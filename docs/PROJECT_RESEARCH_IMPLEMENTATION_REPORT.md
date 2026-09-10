> Historical record from the AutoResearch integration phase. Current standalone layout: [cleanup notes](PROJECT_CLEANUP.md).

# Project Research implementation report

Date: 2026-09-10

## Delivered

Implemented the independent Project Research mode using the local `codex exec` executable. The original
academic entry point keeps its HTTP model routing and Forge workflow. No automatic coding, experiments,
code review, critic, blind review or ar-runtime invocation was added to the new mode.

```text
Collect + normalize + deduplicate
→ Opportunity screen
→ Problem extraction + semantic merge
→ Project ideation + semantic merge
→ Evidence selection from fetched content + competitor pages
→ Structured validation + Python hard gates
→ Score ranking
→ Optional Top-K Red Team
→ JSON and Markdown Project Research Briefs
```

The implementation uses standard-library dataclasses and strict decoding, existing HTTP dependencies,
the shared retry helper, and the existing collector registry. No new Python dependency was added.

## Main changed files

| File | Responsibility/change |
|---|---|
| `project_research.py` | Thin CLI, config loading, Pipeline execution and summary |
| `src/project_research/schemas.py` | Typed artifacts, generated JSON Schemas, strict decoding, claim/reference validation |
| `src/project_research/config.py` | Project defaults, nested local overrides, constraints, Profile and project knowledge loading |
| `src/project_research/codex_client.py` | Isolated Codex processes, stdin, structured results, disabled tools/MCP verification, timeout cleanup, bounded retries and explicit fallback |
| `src/project_research/signals.py` | Registry selection, project queries, normalization, thread identity, bounded HN/Reddit content enrichment |
| `src/project_research/prompts.py` | All research instructions, untrusted-input handling and FACT/INFERENCE/HYPOTHESIS distinctions |
| `src/project_research/ideation.py` | Screening, exact-quote problem extraction, semantic partitioning and source-preserving idea merge |
| `src/project_research/evidence.py` | Public page retrieval, redirect/size checks, evidence selection, quote validation and conservative independent-source grouping |
| `src/project_research/validation.py` | Eight-dimension scoring, recomputed evidence counts, hard rejection and unknown-competitor HOLD rules |
| `src/project_research/ranking.py` | Stable score ranking |
| `src/project_research/red_team.py` | Optional Top-K challenge with no calls when disabled |
| `src/project_research/brief.py` | Authoritative final decisions, typed briefs, Markdown rendering and score breakdown |
| `src/project_research/pipeline.py` | Stage artifacts, hashes, run manifests, process-safe run locks and stage-level resume |
| `src/signal_normalization.py` | Existing normalization extracted without changing its academic behavior |
| `src/research_io.py` | Shared atomic writes and bounded concurrency |
| `src/pipeline_v4.py`, `src/idea_forge/forge.py` | Reuse extracted helpers while retaining old callable names |
| `src/collectors/hackernews_collector.py` | Optional queries, comment threshold, content metadata and strict errors; old defaults preserved |
| `src/collectors/reddit_collector.py` | Optional timestamp metadata and strict error propagation; old defaults preserved |
| `src/collectors/github_trending_collector.py` | Optional keyword filtering and strict errors; old defaults preserved |
| `config/providers.example.json` | Project-only Codex configuration; old HTTP Role table unchanged |
| `.gitignore` | Exclude generated Project Research artifacts |
| `README.md`, `README_CN.md`, `docs/PROJECT_RESEARCH_USAGE.md` | Independent-mode introduction, setup, configuration, commands and limitations |
| `tests/project_research/` | Offline model/source fixtures, decisions, provenance, CLI/process boundaries, collection, recovery and locking |

The user's original Task, research specification and root ProjectProfile were preserved. The existing root
ProjectProfile is read as the fallback profile, so no duplicate personal knowledge file or manifest entry was needed.

## Environment and commands

A repository `.venv` was created with Python 3.12.10 and the existing requirements installed. Python 3.14
initially failed to install the original `editdistance` dependency; using the CI-aligned interpreter resolved it.

The effective local/default Project configuration and existing ProjectProfile loaded successfully.
Minimal config is `{ "project_research": {} }`; this uses the existing Codex login/default model and typed
Project defaults. A fuller example and role overrides are in [the usage guide](PROJECT_RESEARCH_USAGE.md).

```powershell
.\.venv\Scripts\python.exe project_research.py --topic "MCP observability" --top-k 5
.\.venv\Scripts\python.exe project_research.py --topic "MCP observability" --top-k 5 --resume RUN_ID
.\.venv\Scripts\python.exe -m pytest tests/project_research/ -q
```

Keep the same CLI overrides and config for resume. Outputs are under `data/project_research/`.

## Verification

- New Project Research tests: **54 passed**.
- New tests plus relevant existing collector, Forge, provider and retry tests: **152 passed**.
- Real local Codex smoke: **passed**. A read-only, ephemeral, tool-disabled task returned the requested
  structured JSON with exit code 0. It used the configured model; actual model identity was not exposed in
  the consumed events and was recorded as `unknown` rather than guessed.
- The real invocation exposed a plugin MCP configuration edge case. The adapter now supplies valid disabled
  transport entries and verifies the effective MCP list before starting a research task.
- Ruff: **passed**. Python compilation: **passed**. `git diff --check`: **passed**.
- Model reference gate, tracked environment projection, public knowledge manifest and release-tree checks:
  **passed**.
- Existing full-suite Windows baseline before shared-module edits: **692 passed, 252 failed, 5 errors**.
- Final full-suite comparison: **746 passed, 252 failed, 5 errors**; the failed/error test IDs exactly
  matched baseline. All 54 additional passing tests are the new Project Research tests.
- Secret scan: the existing synthetic credential in `tests/test_bringup_contract.py` was flagged even though
  its fingerprint is already allowlisted. The Windows backslash path does not match the allowlist's slash
  path in the existing scanner. No new credential match was reported; the scanner was not weakened or bypassed.

The old suite assumes Linux/Bash/fcntl and symlink behavior unavailable in this Windows environment. WSL is
not installed. Full Linux CI validation remains outstanding; the report does not claim the full suite is green.
The complete Project Pipeline was exercised with synthetic data and mocked models/collectors. A live community
research run was not performed; the real-model verification was a separate minimal Codex smoke test.

## Known limitations

- GitHub Issue/Discussion search and exhaustive competitor discovery are not implemented. First-version
  competitor leads come from ideation and originating posts, followed by real page retrieval.
- GitHub repository metadata not actually collected remains unknown; HN/Reddit comment enrichment is bounded.
- Evidence retrieval uses a capped lexical priority after preserving originating sources and competitor pages.
  Its coverage limit is reported in the Evidence Pack and Brief.
- Exact quotes and valid references establish traceability. Semantic relevance/entailment still relies on
  model judgment and human inspection; fabricated certainty is discouraged by prompts and typed claim categories.
- Recovery is stage-level. A failure within a stage may repeat successful requests from that incomplete stage.
- Red Team using the same model is a separate-context challenge, not independent model consensus.

No business code was committed or published as part of this implementation task.
