"""Lazy source registry for community and optional background evidence."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Window:
    time_filter: str = "month"
    time_filter_days: int = 30
    arxiv_days: int = 7
    hf_days: int = 7


@dataclass(frozen=True)
class Channel:
    key: str
    kind: str
    module: str
    fetch: Callable[[Any, Window], list | dict[str, list]]
    required: bool = False


GITHUB_SINCE = {"month": "monthly", "week": "weekly", "year": "monthly"}

CHANNELS = (
    Channel("reddit", "community", "reddit_collector",
            lambda m, w: m.search_reddit_research("LocalLLaMA", "agent", w.time_filter)),
    Channel("hackernews", "community", "hackernews_collector",
            lambda m, w: m.get_hn_discussed(time_filter_days=w.time_filter_days)),
    Channel("github_trending", "community", "github_trending_collector",
            lambda m, w: m.collect_trending(since=GITHUB_SINCE.get(w.time_filter, "monthly"))),
    Channel("arxiv", "academic", "arxiv_collector",
            lambda m, w: m.collect_recent_papers(days_back=w.arxiv_days, max_per_category=20)),
    Channel("hf_papers", "academic", "hf_papers_collector",
            lambda m, w: m.collect_daily_papers(days_back=w.hf_days)),
    Channel("emergent_mind", "academic", "emergent_mind_collector", lambda m, w: m.collect_emergent_mind()),
    Channel("paper_digest", "academic", "paper_digest_collector", lambda m, w: m.collect_paper_digest()),
    Channel("rss", "media", "rss_collector", lambda m, w: m.collect_all_feeds()[0]),
    Channel("influential_voices", "academic", "influential_voices",
            lambda m, w: {"blogs": m.collect_research_blogs(max_days=w.time_filter_days),
                          "conferences": m.collect_conference_highlights()}),
    Channel("openreview", "academic", "openreview_collector", lambda m, w: m.collect_all_venues()),
    Channel("jina_chinese_media", "media", "jina_chinese_media",
            lambda m, w: m.collect_chinese_media(first_run=False)),
)


def collection_channels() -> tuple[Channel, ...]:
    return CHANNELS


def collect(channel: Channel, window: Window) -> dict[str, list]:
    items = channel.fetch(importlib.import_module("collectors." + channel.module), window)
    return items if isinstance(items, dict) else {"": items}
