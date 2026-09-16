# IdeaProbe

Evidence-driven project idea research powered by the local Codex CLI.

[中文说明](README_CN.md) · [Usage](docs/PROJECT_RESEARCH_USAGE.md) · [Architecture](ARCHITECTURE.md)

IdeaProbe searches public developer discussions, extracts problems, proposes small projects, checks evidence and competitors, and produces GO / HOLD / REJECT briefs. Python owns collection and decision rules; isolated local `codex exec` calls perform structured analysis.

## Quick start

Use Python 3.12 and install/authenticate Codex CLI separately.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
codex login
.\.venv\Scripts\python.exe project_research.py --topic "AI agent context management"
```

On Linux, use `python3.12 -m venv .venv` and `.venv/bin/python`.

Configuration defaults live in [config/project.example.json](config/project.example.json). Put overrides in ignored `config/project.local.json`, or supply `--config path/to/config.json`. Existing project blocks in `config/providers.local.json` remain readable. `IDEAPROBE_CONFIG` selects an explicit file; `AUTORESEARCH_CONFIG` is retained as a fallback.

The example's full budget can require many Codex calls. See the [real-run evaluation](docs/PROJECT_RESEARCH_AGENT_CONTEXT_EVALUATION.md) before choosing a routine budget.

## Workflow

Signals → screening → problems → deduplication → ideas → evidence → validation → ranking → optional Red Team → briefs.

- Default source: Hacker News, searched using your `--topic` and optional explicit `queries`.
- Reddit and GitHub Trending require explicit opt-in. Bulk academic, news and blog collectors have been removed.
- See the [source strategy](docs/PROJECT_SOURCE_STRATEGY.md) for the existing-idea focus and proposed additions.
- [ProjectProfile.md](ProjectProfile.md) describes your skills, constraints and preferred opportunities.
- JSON checkpoints and Markdown briefs are saved under ignored `data/project_research/`.
- Resume with the same configuration and `--resume RUN_ID`.
- Zero demand evidence and hard rejections prevent GO. Same-thread or known related evidence is conservatively grouped.
- Red Team can downgrade a decision. It uses an isolated context, which does not imply an independent model.

Exact quotations establish traceability, not market validation. Source access can fail, competitor coverage is incomplete, and demand relevance still needs human review.

## Development

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/secret_scan.py .
```

Tests run offline. CI covers Python 3.12 on Windows and Linux; real model calls are a separate check.

## Origin and license

Maintained by MaKik. This project derives parts of its collectors and utilities from [AutoResearch](https://github.com/EvoMap/AutoResearch). The original academic pipeline, Forge, experiment runtime and dashboards have been removed.

See [LICENSE](LICENSE), [NOTICE](NOTICE) and the preserved [upstream citation](docs/UPSTREAM_CITATION.cff). See [cleanup notes](docs/PROJECT_CLEANUP.md) for the standalone transition.
