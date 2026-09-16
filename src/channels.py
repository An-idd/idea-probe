"""Lazy source registry for focused developer idea research."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Window:
    time_filter: str = "month"
    time_filter_days: int = 30


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
)


def collection_channels() -> tuple[Channel, ...]:
    return CHANNELS


def collect(channel: Channel, window: Window) -> dict[str, list]:
    items = channel.fetch(importlib.import_module("collectors." + channel.module), window)
    return items if isinstance(items, dict) else {"": items}
