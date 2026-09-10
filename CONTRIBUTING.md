# Contributing to IdeaProbe

Use Python 3.12 with a virtual environment. Install `requirements-dev.txt`; optional source dependencies are in `requirements-sources.txt`.

Before submitting a change:

```text
python -m pytest tests/ -q
python -m ruff check .
python -m compileall -q project_research.py src scripts
python scripts/secret_scan.py .
```

Keep tests offline. A live Codex run consumes the user's account limits and should be deliberate. For evidence handling, test malformed citations and failure recovery as well as successful output.

Use small commits with Conventional Commit titles. Explain the behavior changed and the checks run. Preserve source attribution and avoid committing local configurations, profiles containing private information, research outputs or credentials.

Optional hooks: install `pre-commit`, then run `pre-commit install` and `pre-commit install --hook-type pre-push`.
