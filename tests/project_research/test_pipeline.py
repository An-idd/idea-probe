import importlib.util
import json
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

import pytest

import research_fixtures

from project_research import brief, ideation, red_team
from project_research.config import load_knowledge, load_profile
from project_research.pipeline import run_pipeline
from project_research.schemas import MergeResult, ProjectBrief, RedTeamResult, decode
from project_research.validation import decide
from research_io import atomic_write_json

case = research_fixtures.case
scenario = research_fixtures.scenario


def test_red_team_disabled(case):
    scenario, idea, _, pack, assessment = case
    result = decide(idea, pack, assessment, scenario.config)
    scenario.config.red_team.enabled = False
    assert red_team.red_team_top_k([result], [idea], [pack], scenario.config,
                                   lambda *a: pytest.fail("Red Team called")) == []


def test_red_team_top_k(case):
    scenario, idea, _, pack, assessment = case
    result = decide(idea, pack, assessment, scenario.config)
    ideas = [replace(idea, id=str(i)) for i in range(10)]
    packs = [replace(pack, idea_id=str(i)) for i in range(10)]
    results = [replace(result, idea_id=str(i)) for i in range(10)]
    reviews = red_team.red_team_top_k(results, ideas, packs, scenario.config, scenario.ask)
    assert [r.idea_id for r in reviews] == ["0", "1", "2"]
    assert sum(cls is RedTeamResult for _, cls in scenario.calls) == 3


def test_pipeline_smoke(scenario, tmp_path):
    state = run_pipeline(scenario.config, tmp_path, ask=scenario.ask,
                         collector=lambda _: scenario.signals, evidence_provider=scenario.provider)
    assert state.status == "completed" and state.counts["go"] == 1
    output = tmp_path / "data/project_research"
    raw = json.loads((output / "briefs" / f"{state.id}.json").read_text(encoding="utf-8"))
    item = decode(ProjectBrief, raw[0])
    assert item.evidence.independent_evidence_count == 2
    assert len(item.problems[0].observations) == 2
    markdown = brief.render_markdown(item)
    assert "Final Decision\n\n**GO**" in markdown
    assert "https://www.reddit.com/" in markdown
    assert "[HYPOTHESIS]" in markdown
    assert len(list((output / "briefs").glob("*.md"))) == 1
    assert not (tmp_path / "data/verified").exists()
    resumed = run_pipeline(scenario.config, tmp_path, resume=state.id,
                           ask=lambda *a: pytest.fail("Completed stage rerun"),
                           collector=lambda _: pytest.fail("Collector rerun"))
    assert resumed.counts == state.counts


def test_red_team_failure_preserves_stages_and_resume(scenario, tmp_path):
    scenario.fail_red = True
    with pytest.raises(RuntimeError, match="red team unavailable"):
        run_pipeline(scenario.config, tmp_path, ask=scenario.ask,
                     collector=lambda _: scenario.signals, evidence_provider=scenario.provider)
    manifest = next((tmp_path / "data/project_research/runs").glob("*.json"))
    state = json.loads(manifest.read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert "validation" in state["completed_stages"]
    assert "red_team" not in state["completed_stages"]
    scenario.fail_red = False
    scenario.calls.clear()
    result = run_pipeline(scenario.config, tmp_path, resume=state["id"], ask=scenario.ask,
                          collector=lambda _: pytest.fail("Collector rerun"))
    assert result.status == "completed"
    assert {role for role, _ in scenario.calls} == {"project_red_team", "project_brief_writer"}
    changed = deepcopy(scenario.config)
    changed.topic = "changed"
    with pytest.raises(ValueError, match="differ"):
        run_pipeline(changed, tmp_path, resume=state["id"], ask=scenario.ask)
    evidence = tmp_path / "data/project_research/evidence" / f"{state['id']}.json"
    evidence.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact changed"):
        run_pipeline(scenario.config, tmp_path, resume=state["id"], ask=scenario.ask)


def test_empty_pipeline_does_not_call_codex(scenario, tmp_path):
    state = run_pipeline(scenario.config, tmp_path, collector=lambda _: [],
                         ask=lambda *a: pytest.fail("LLM invoked with no signals"))
    assert state.status == "completed" and state.counts["briefs"] == 0


def test_dedup_requires_a_partition(case):
    scenario, _, problems, _, _ = case
    duplicate = replace(problems[0], id="other")
    with pytest.raises(ValueError, match="partition"):
        ideation.deduplicate_problems(problems + [duplicate], scenario.config,
                                     lambda *a: MergeResult([]))


def test_atomic_write_failure_keeps_previous_file(tmp_path, monkeypatch):
    import research_io
    path = tmp_path / "checkpoint.json"
    atomic_write_json(path, {"completed": 1})
    monkeypatch.setattr(research_io.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk error")))
    with pytest.raises(OSError, match="disk error"):
        atomic_write_json(path, {"completed": 2})
    assert json.loads(path.read_text()) == {"completed": 1}
    assert not list(tmp_path.glob("*.tmp"))


def test_profile_and_knowledge_boundaries(scenario, tmp_path, caplog):
    assert load_profile(tmp_path, scenario.config) == ""
    assert "empty profile" in caplog.text
    (tmp_path / "ProjectProfile.md").write_text("Python developer", encoding="utf-8")
    assert load_profile(tmp_path, scenario.config) == "Python developer"
    scenario.config.knowledge_directions = ["../../secret"]
    with pytest.raises(ValueError, match="escapes"):
        load_knowledge(tmp_path, scenario.config)


def test_new_cli_parses_and_runs_without_http_roles(monkeypatch, scenario, tmp_path):
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("project_entry", root / "project_research.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"project_research": asdict(scenario.config)}), encoding="utf-8")
    captured = []
    def run(config, root, **kwargs):
        captured.append(config)
        return run_pipeline(config, tmp_path, ask=scenario.ask,
                            collector=lambda _: scenario.signals, evidence_provider=scenario.provider)
    monkeypatch.setattr(module, "run_pipeline", run)
    assert module.main(["--config", str(config_path), "--topic", "工具", "--no-red-team", "--top-k", "1"]) == 0
    assert captured[0].topic == "工具" and not captured[0].red_team.enabled


def test_run_lock_prevents_concurrent_resume(tmp_path):
    from project_research.pipeline import run_lock
    path = tmp_path / "run.lock"
    with run_lock(path):
        with pytest.raises(RuntimeError, match="already active"):
            with run_lock(path):
                pytest.fail("Second process acquired the run")
    with run_lock(path):
        pass  # A released lock does not block subsequent resume.
