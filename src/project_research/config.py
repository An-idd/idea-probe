"""IdeaProbe settings and local JSON configuration, independent of model gateways."""

from __future__ import annotations

import logging
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .schemas import decode

ROLES = ("project_ideator", "project_validator", "project_brief_writer", "project_red_team")


@dataclass
class CodexConfig:
    executable: str = "codex"
    models: list[str] = field(default_factory=list)
    timeout_seconds: int = 300
    attempts: int = 2
    max_concurrency: int = 1
    reasoning_effort: str = ""


@dataclass
class RedTeamConfig:
    enabled: bool = True
    top_k: int = 3


@dataclass
class Thresholds:
    go: int = 75
    hold: int = 60


@dataclass
class Sources:
    github: bool = False
    hackernews: bool = True
    reddit: bool = False


@dataclass
class ProjectConfig:
    enabled: bool = True
    lookback_days: int = 30
    max_signals: int = 200
    max_problems: int = 30
    max_ideas: int = 20
    top_k: int = 5
    min_independent_evidence: int = 2
    batch_size: int = 10
    topic: str = ""
    profile_path: str = ""
    required_sources: list[str] = field(default_factory=list)
    subreddits: list[str] = field(default_factory=lambda: ["LocalLLaMA", "selfhosted", "opensource", "Python"])
    queries: list[str] = field(default_factory=list)
    knowledge_directions: list[str] = field(default_factory=list)
    max_comments: int = 5
    max_competitor_pages: int = 3
    max_document_chars: int = 6000
    max_evidence_documents: int = 30
    codex: CodexConfig = field(default_factory=CodexConfig)
    roles: dict[str, list[str]] = field(default_factory=lambda: {role: [] for role in ROLES})
    red_team: RedTeamConfig = field(default_factory=RedTeamConfig)
    decision_thresholds: Thresholds = field(default_factory=Thresholds)
    sources: Sources = field(default_factory=Sources)

    def validate(self) -> None:
        for name in ("lookback_days", "max_signals", "max_problems", "max_ideas", "batch_size",
                     "min_independent_evidence", "max_document_chars", "max_evidence_documents"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")
        for name in ("top_k", "max_comments", "max_competitor_pages"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")
        if not 0 <= self.decision_thresholds.hold < self.decision_thresholds.go <= 100:
            raise ValueError("Require 0 <= hold < go <= 100")
        if self.red_team.top_k < 0:
            raise ValueError("red_team.top_k must be nonnegative")
        if min(self.codex.timeout_seconds, self.codex.attempts, self.codex.max_concurrency) < 1:
            raise ValueError("Codex timeout, attempts and concurrency must be positive")
        if not self.codex.executable.strip():
            raise ValueError("codex.executable is empty")
        if set(self.roles) - set(ROLES):
            raise ValueError("Unknown Project Research role")
        if any(not name.strip() for name in self.codex.models + [m for ms in self.roles.values() for m in ms]):
            raise ValueError("Model names cannot be empty")
        if any(not re.fullmatch(r"[A-Za-z0-9_]+", name) for name in self.subreddits):
            raise ValueError("Invalid subreddit name")
        if set(self.required_sources) - {"github", "hackernews", "reddit"}:
            raise ValueError("Unknown required source")
        if any(not getattr(self.sources, name) for name in self.required_sources):
            raise ValueError("A required source must be enabled")


def load_project_config(raw: dict) -> ProjectConfig:
    # Accept old disabled flags, but never silently ignore an enabled removed source.
    if isinstance(raw.get("sources"), dict):
        sources = dict(raw["sources"])
        for name in ("academic", "media"):
            if name in sources:
                if sources.pop(name) is not False:
                    raise ValueError(f"Source {name} has been removed; remove it from sources")
        raw = {**raw, "sources": sources}
    config = decode(ProjectConfig, raw)
    config.validate()
    return config


def load_config(root: Path, explicit: Path | None = None) -> ProjectConfig:
    """Explicit files stand alone; local project settings overlay the example otherwise."""
    def read(path: Path) -> dict:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict) or not isinstance(raw.get("project_research", {}), dict):
            raise ValueError(f"{path}: expected a project_research object")
        return raw.get("project_research", {})

    def merge(base: dict, override: dict) -> dict:
        result = dict(base)
        for key, value in override.items():
            if isinstance(result.get(key), dict) and isinstance(value, dict):
                result[key] = merge(result[key], value)
            else:
                result[key] = value
        return result

    if explicit is not None:
        return load_project_config(read(explicit))
    example = root / "config/project.example.json"
    raw = read(example) if example.is_file() else {}
    # Read only the project block of an existing local file; never migrate or copy credentials.
    for local in (root / "config/project.local.json", root / "config/providers.local.json"):
        if local.is_file():
            raw = merge(raw, read(local))
            break
    return load_project_config(raw)


def load_profile(root: Path, config: ProjectConfig) -> str:
    paths = ([root / config.profile_path] if config.profile_path else
             [root / "knowledge_base/project/project_profile.md", root / "ProjectProfile.md"])
    for path in paths:
        if path.is_file():
            logging.info("[Profile] %s", path)
            return path.read_text(encoding="utf-8")
    logging.warning("[Profile] missing; continuing with an empty profile")
    return ""


def load_knowledge(root: Path, config: ProjectConfig) -> str:
    base = (root / "knowledge_base/project").resolve()
    texts = []
    for direction in config.knowledge_directions:
        path = (base / f"{direction}.md").resolve()
        if not path.is_relative_to(base):
            raise ValueError("Project knowledge path escapes knowledge_base/project")
        if path.is_file():
            texts.append(path.read_text(encoding="utf-8"))
        else:
            logging.warning("[Knowledge] missing %s", path)
    return "\n\n".join(texts)
