"""Explicit stages with immutable run inputs and atomic, resumable artifacts."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from research_io import atomic_write_json, atomic_write_text

from .config import ProjectConfig, load_knowledge, load_profile
from .schemas import RunState, decode, payload

T = TypeVar("T")
SCHEMA_VERSION = "project-research-1"


@contextmanager
def run_lock(path: Path):
    """OS locks release on process exit, so a crashed run can be resumed."""
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        try:
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("This run is already active") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def run_pipeline(config: ProjectConfig, root: Path, *, output_dir: Path | None = None,
                 resume: str | None = None, ask=None, collector=None, evidence_provider=None) -> RunState:
    # Keep collection and model dependencies lazy for CLI/config inspection.
    from . import brief, evidence, ideation, prompts, ranking, red_team, validation
    from .codex_client import CodexClient
    from .schemas import EvidencePack, Problem, ProjectBrief, ProjectIdea, RedTeamRecord, Signal, ValidationResult
    from .signals import collect_signals

    config.validate()
    if not config.enabled:
        raise ValueError("project_research.enabled is false")
    profile, knowledge = load_profile(root, config), load_knowledge(root, config)
    fingerprint = hashlib.sha256(json.dumps(
        [SCHEMA_VERSION, asdict(config), profile, knowledge, prompts.VERSION], sort_keys=True,
        ensure_ascii=False).encode("utf-8")).hexdigest()
    run_id = resume or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("resume must be a run ID, not a path")
    output = (output_dir or root / "data/project_research").resolve()
    manifest = output / "runs" / f"{run_id}.json"
    with run_lock(output / "runs" / f"{run_id}.lock"):
        if resume:
            state = decode(RunState, json.loads(manifest.read_text(encoding="utf-8")))
            if state.fingerprint != fingerprint or state.id != run_id:
                raise ValueError("Checkpoint configuration/profile/prompts differ; start a new run")
        else:
            state = RunState(run_id, datetime.now(timezone.utc).isoformat(), fingerprint, asdict(config))
        client = CodexClient(config.codex, config.roles) if ask is None else ask
        previous_calls = list(state.model_calls)

        def save():
            state.model_calls = previous_calls + list(getattr(client, "calls", []))
            atomic_write_json(manifest, asdict(state))

        def stage(name: str, cls: type[T], action: Callable[[], T]) -> T:
            path = output / name / f"{run_id}.json"
            if name in state.completed_stages:
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != state.artifact_hashes[name]:
                    raise ValueError(f"Checkpoint artifact changed: {name}")
                logging.info("[Resume] %s", name)
                return decode(cls, json.loads(content))
            logging.info("[%s] starting", name)
            result = action()
            atomic_write_json(path, payload(result))
            state.artifact_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            state.completed_stages.append(name)
            if isinstance(result, list):
                state.counts[name] = len(result)
            save()
            logging.info("[%s] %s completed", name, len(result) if isinstance(result, list) else "")
            return result

        state.status, state.error = "running", ""
        save()
        try:
            signals = stage("signals", list[Signal], lambda: (collector or collect_signals)(config))
            screened = stage("screen", list[Signal], lambda: ideation.screen_opportunities(signals, config, client))
            extracted = stage("extract_problem", list[Problem],
                              lambda: ideation.extract_problems(screened, config, client))
            problems = stage("problems", list[Problem],
                             lambda: ideation.deduplicate_problems(extracted, config, client))
            ideas = stage("ideas", list[ProjectIdea],
                          lambda: ideation.generate_project_ideas(problems, config, profile, knowledge, client))
            packs = stage("evidence", list[EvidencePack],
                          lambda: evidence.collect_evidence(ideas, problems, signals, config, client,
                                                            evidence_provider))
            validated = stage("validation", list[ValidationResult],
                              lambda: validation.validate_ideas(ideas, packs, config, profile, client))
            ranked = stage("ranking", list[ValidationResult], lambda: ranking.rank_ideas(validated))
            reviews = stage("red_team", list[RedTeamRecord],
                            lambda: red_team.red_team_top_k(ranked, ideas, packs, config, client))
            briefs = stage("briefs", list[ProjectBrief],
                           lambda: brief.generate_briefs(ranked, ideas, problems, packs, reviews, config, client))
            for item in briefs:
                # Recreate a missing Markdown export on resume without any LLM call.
                atomic_write_text(output / "briefs" / f"{run_id}_{item.idea.id}.md", brief.render_markdown(item))
            decisions = {item.idea.id: item.final_decision for item in briefs}
            for item in ranked:
                decisions.setdefault(item.idea_id, brief.final_decision(item, reviews))
            state.counts.update({name.lower(): list(decisions.values()).count(name)
                                 for name in ("GO", "HOLD", "REJECT")})
            state.status = "completed"
            save()
            logging.info("[Done] run=%s GO=%s HOLD=%s REJECT=%s", run_id,
                         state.counts["go"], state.counts["hold"], state.counts["reject"])
            return state
        except BaseException as exc:
            state.status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            state.error = f"{type(exc).__name__}: {exc}"
            save()
            logging.error("[Failed] run=%s; completed stages preserved: %s", run_id, state.error)
            raise
