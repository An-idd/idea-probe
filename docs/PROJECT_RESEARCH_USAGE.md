# IdeaProbe — local Codex CLI

Project Research discovers developer problems and produces evidence-backed project briefs. It runs as a standalone project-research workflow; it does not execute coding tasks or experiments.

Project Research 用于开发前的机会研究，输出 GO / HOLD / REJECT 和可追溯的 Brief。
Python 负责采集、引用校验、独立证据计数、最终决策与恢复；本机 `codex exec` 负责结构化分析。

## Environment / 环境

Use Python 3.12 and a repository-local `.venv`. This matches the existing CI Python version and avoids
the `editdistance` installation failure observed with Python 3.14 on Windows.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
codex login
.\.venv\Scripts\python.exe project_research.py --topic "MCP observability"
```

Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
codex login
.venv/bin/python project_research.py --topic "MCP observability"
```

Install Codex separately and put its executable on PATH, or configure `codex.executable` below.
Existing Codex login and default model configuration are reused. No old HTTP provider credentials or
three-model panel are required for this mode. Running research consumes the limits of your Codex account.
The CLI must support the documented `exec`, MCP listing and configuration switches used by this adapter;
an incompatible CLI fails with a recorded configuration error.

Codex uses structured output and independent ephemeral tasks. Shell execution, web search, apps, plugins,
hooks, multi-agent features and configured MCP servers are disabled for these model calls. MCP disablement
is checked before invoking the model. Source collection is performed by Python. A read-only sandbox alone
would not disable remote connector tools. The adapter never copies or saves Codex credentials.

Official reference: [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).

## Configuration / 配置

Normal configuration comes from `config/project.local.json`, overlaid on `config/project.example.json`.
Only the `project_research` block is consumed. An explicit `--config` file (or `IDEAPROBE_CONFIG`) uses that file directly.
`AUTORESEARCH_CONFIG` and the project block of `config/providers.local.json` remain legacy fallbacks. Missing nested Project settings receive their typed defaults.
Local nested values override example settings. Explicit files use typed defaults for omitted values.

Minimal standalone config:

```json
{
  "project_research": {
    "codex": {
      "executable": "codex",
      "models": [],
      "timeout_seconds": 300,
      "attempts": 2,
      "max_concurrency": 1
    },
    "red_team": {"enabled": true, "top_k": 3}
  }
}
```

Empty `models` uses the configured Codex model. An explicit list contains CLI model names in fallback order,
not aliases from the old HTTP provider registry. Optional role-specific lists live under
`project_research.roles`: `project_ideator`, `project_validator`, `project_brief_writer`, `project_red_team`.
An empty role list inherits `codex.models`. One model may serve all roles. The same model's Red Team task is
a separate-context challenge, not independent model consensus.

Default budgets: 30-day lookback, 200 signals, 30 problems, 20 ideas, 5 briefs, 2 independent demand sources,
3 Red Team candidates. Batches contain 10 records. At most 5 top-level comments per supported community
signal, 3 competitor pages per idea, 6,000 characters per document, and 30 documents per idea's evidence
selection are used. Adjust `max_comments`, `max_competitor_pages`, `max_document_chars`,
`max_evidence_documents` and the main stage limits to control collection and model workload.

The default source is Hacker News. Supply `--topic` or nonempty `queries` describing your idea; no generic
search terms are added automatically. Explicit `queries` are additional searches, so keep them relevant.
Reddit and GitHub Trending are opt-in through `--sources` or JSON settings. Reddit was blocked during the
2026-09-14 check; Trending is useful for discovery but cannot establish demand. Academic/media collectors and
`requirements-sources.txt` have been removed. Old `academic: false` / `media: false` settings are accepted;
enabling either removed group fails with a migration error. Set `required_sources` explicitly to fail a run when a selected source fails.
If every enabled source fails, the run fails rather than claiming successful empty research.

These changed defaults/configuration fields require a new run; old artifacts remain readable, but their
configuration fingerprint will not match for resume. See [source strategy](PROJECT_SOURCE_STRATEGY.md) for
proposed additions. A full existing-idea validation mode and user-supplied evidence import are not implemented yet.

## Project Profile

Lookup order:

1. An explicitly configured `profile_path` or CLI `--profile`.
2. `knowledge_base/project/project_profile.md`.
3. The repository's existing root `ProjectProfile.md`.

An explicit missing path does not silently select a different profile. Missing profiles produce a warning
and an empty profile. The chosen profile is supplied to ideation and feasibility validation.
`knowledge_directions` optionally names Markdown stems below `knowledge_base/project/`; paths cannot escape
that directory. Review selected knowledge files for private information before publishing them.

## Commands / 运行与恢复

```powershell
.\.venv\Scripts\python.exe project_research.py --topic "agent context version history"
.\.venv\Scripts\python.exe project_research.py --topic "MCP observability" --top-k 5 --no-red-team
.\.venv\Scripts\python.exe project_research.py --topic "MCP observability" --sources github,hackernews --lookback-days 7
.\.venv\Scripts\python.exe project_research.py --config path/to/project-config.json
.\.venv\Scripts\python.exe project_research.py --resume RUN_ID
```

Use the same topic, config and CLI overrides when resuming. The run manifest records the effective settings.
Changing the settings/profile/prompt version requires a new run. Resume verifies artifact hashes and skips
completed stages. A failed stage is retried as a whole; successful requests within an incomplete stage may
be repeated. Pipeline checkpoints are independent of Codex chat history.

## Outputs / 输出

All artifacts live under `data/project_research/` (ignored by Git), or a supplied `--output-dir`:

- `signals/`, `screen/`, `extract_problem/`, `problems/`, `ideas/`.
- `evidence/`, `validation/`, `ranking/`, `red_team/`.
- `briefs/<RUN_ID>.json` and `briefs/<RUN_ID>_<IDEA_ID>.md`.
- `runs/<RUN_ID>.json`: state, effective config, stage hashes, counts, failures and available model-call metadata.

Files are written atomically. Run locks are released by the operating system after a process exits.
If Red Team fails, prior evidence/validation remains intact; failure is not treated as PASS.
When the CLI does not expose actual model identity, metadata says `unknown`, alongside the requested model.

## Decision rules / 决策规则

Eight bounded dimensions total 100: Problem Reality 20, Evidence Strength 20, Competitor Gap 15,
Differentiation 15, Feasibility 10, MVP Clarity 10, Distribution 5, Maintenance 5.
Higher Maintenance points mean lower maintenance risk. Thresholds default to GO candidate ≥75, HOLD ≥60,
REJECT <60, subject to the following stronger gates:

- Zero external demand evidence, no target user, no differentiation, wrapper-only or other confirmed hard
  rejection means REJECT regardless of score.
- Fewer independent demand sources than configured, or unverified competitor coverage/gap, prevents GO.
- Same-thread comments, repeated quotes, known same authors and same repositories are conservatively grouped.
- Competitor pages, repository descriptions and popularity metrics cannot increase demand evidence count.
- Evidence quotations must occur verbatim in retained source documents. Claim citations must reference
  available evidence; unsupported claims must be HYPOTHESIS.
- Red Team may downgrade decisions; PASS cannot override a hard rejection. Brief prose cannot change decisions.

The source-to-claim interpretation is still model-assisted: exact quotation and reference checks establish
traceability, not automatic proof that a quotation entails every model inference. Humans should inspect the
quoted material before acting on a GO decision.

## Current limitations / 已知限制

- No GitHub Issue/Discussion search or exhaustive competitor search yet. Competitor candidates come from
  model-proposed leads and originating posts' links; only successfully fetched pages become evidence.
- Comment collection is limited to available top-level comments. HN/Reddit access restrictions can reduce coverage.
- GitHub Trending supports its own daily/weekly/monthly windows, not complete arbitrary historical lookbacks.
- Corroboration retrieval is bounded and uses a simple lexical priority after source provenance; it may miss
  semantically related evidence. The brief reports retrieval truncation and fetch failures.
- Repository stars, archived status and update dates remain unknown unless actually collected; no metadata is invented.
- Stage-level recovery is supported; per-request checkpoints within a failed stage are not implemented.
- CI targets Python 3.12 on Windows and Linux. Live source availability is not covered by offline tests.

## Verification / 验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_research/ -q
.\.venv\Scripts\python.exe -m ruff check .
```

Tests use synthetic data, mocked collectors/model responses and a fake CLI subprocess. They do not contact
external services. A real Codex smoke test is a separate verification step, not part of the offline suite.
