"""IdeaProbe: discover evidence-backed project opportunities using the local Codex CLI."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from project_research.config import load_config  # noqa: E402
from project_research.pipeline import run_pipeline  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Explicit config file (otherwise existing local/default config)")
    parser.add_argument("--topic")
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--lookback-days", type=int)
    parser.add_argument("--sources", help="Comma-separated github,hackernews,reddit (default: hackernews)")
    parser.add_argument("--no-red-team", action="store_true")
    parser.add_argument("--resume", help="Run ID printed by an earlier run; use the same config/CLI options")
    parser.add_argument("--profile", help="Project profile path")
    parser.add_argument("--output-dir", type=Path, help="Override data/project_research")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        env_config = os.environ.get("IDEAPROBE_CONFIG") or os.environ.get("AUTORESEARCH_CONFIG")
        explicit = args.config or (Path(env_config) if env_config else None)
        config = load_config(ROOT, explicit)
        overrides = {key: getattr(args, key) for key in ("topic", "top_k", "lookback_days")
                     if getattr(args, key) is not None}
        if args.profile:
            overrides["profile_path"] = args.profile
        config = replace(config, **overrides)
        if args.sources is not None:
            names = set(args.sources.split(","))
            known = {"github", "hackernews", "reddit"}
            if not names or names - known:
                raise ValueError("Unknown/empty --sources; use github,hackernews,reddit")
            config.sources = type(config.sources)(**{name: name in names for name in known})
        if args.no_red_team:
            config.red_team.enabled = False
        state = run_pipeline(config, ROOT, output_dir=args.output_dir, resume=args.resume)
        print(f"Run: {state.id}\nStatus: {state.status}\nCounts: {state.counts}")
        print(f"Briefs: {(args.output_dir or ROOT / 'data/project_research') / 'briefs'}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        logging.error("Project Research failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
