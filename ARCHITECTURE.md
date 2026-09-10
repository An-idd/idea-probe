# IdeaProbe architecture

## Execution

`project_research.py` parses CLI flags and loads the project configuration. It calls `src/project_research/pipeline.py`, which owns ten atomic, resumable stages.

| Stage | Responsibility |
|---|---|
| signals | Fetch, normalize and enrich public source records |
| screen | Select topic-relevant problems and workarounds |
| extract_problem | Extract problems with exact source quotations |
| problems | Merge overlapping problems while preserving observations |
| ideas | Propose and merge constrained project hypotheses |
| evidence | Fetch bounded competitor pages and validate quotations |
| validation | Assess eight dimensions and apply evidence gates |
| ranking | Sort validated candidates deterministically |
| red_team | Challenge top candidates in isolated contexts |
| briefs | Render authoritative decisions to JSON and Markdown |

## Boundaries

- `config.py`: typed settings, JSON file precedence, project profile and knowledge loading.
- `schemas.py`: shared dataclasses, structured output schemas and claim validation.
- `codex_client.py`: local subprocess calls, model selection, timeouts, tool isolation and usage records.
- `prompts.py`: stage instructions and serialized input material.
- `src/channels.py` and `src/collectors/`: lazy community and optional background sources.
- `api_retry.py`, `signal_normalization.py`, `research_io.py`: HTTP retries, normalization and atomic I/O.

The model cannot change Python's final decision rules. Quotation and identity checks establish traceability; they do not automatically establish semantic support or market demand.

Codex runs independently in temporary directories with tools disabled. Python performs network collection. Competitor redirects are checked for public destinations and response size is bounded.

## Stored state

Runs, stage hashes, JSON artifacts and Markdown briefs live under `data/project_research/`. A run lock prevents simultaneous resume. Configuration/profile/prompt-version changes require a new run. Recovery is stage-level.

Project knowledge is read only from `knowledge_base/project/`. The root `ProjectProfile.md` remains a supported profile. Research state paths and artifact formats are retained for existing runs.

## Standalone distribution

There is no HTTP model gateway, academic idea-generation entry point, Forge, experiment runtime, scheduler or dashboard. Academic/media collectors remain optional inputs to project research and do not count as community demand.
