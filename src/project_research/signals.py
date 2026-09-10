"""Project queries over the existing collector registry, plus bounded source content."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from itertools import islice, zip_longest
from urllib.parse import parse_qs, urlsplit, urlunsplit

from bs4 import BeautifulSoup

import channels
from api_retry import http_get
from signal_normalization import normalize_post, normalize_title

from .config import ProjectConfig
from .schemas import Document, Signal, stable_id


def clean_text(text: str) -> str:
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def canonical_url(url: str) -> str:
    p = urlsplit(url)
    if p.scheme not in ("https", "http") or not p.hostname or p.username or p.password:
        raise ValueError("Expected public HTTP(S) source URL")
    path = p.path.rstrip("/") or "/"
    # Preserve identity-bearing queries such as HN's ?id=; remove only tracking fields.
    query = "&".join(q for q in p.query.split("&") if q and not q.lower().startswith(("utm_", "ref=")))
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, query, ""))


def thread_key(url: str) -> str:
    p = urlsplit(canonical_url(url))
    host, parts = p.hostname, p.path.strip("/").split("/")
    if host in ("reddit.com", "www.reddit.com", "old.reddit.com") and "comments" in parts:
        i = parts.index("comments")
        if len(parts) > i + 1:
            return "reddit:" + parts[i + 1]
    if host == "news.ycombinator.com" and parse_qs(p.query).get("id"):
        return "hn:" + parse_qs(p.query)["id"][0]
    if host == "github.com" and len(parts) >= 4 and parts[2] in ("issues", "discussions", "pull"):
        return "github:" + "/".join(parts[:4]).lower()
    return canonical_url(url)


def document(signal: Signal, text: str, url: str = "", author: str = "") -> Document:
    url = canonical_url(url or signal.url)
    return Document(stable_id("doc", url, text), signal.id, signal.source, url, text,
                    thread_key(signal.url), author or signal.author,
                    str(signal.repository.get("name") or ""), datetime.now(timezone.utc).isoformat(),
                    signal.source_type)


def normalize_signal(item: dict, kind: str, config: ProjectConfig) -> Signal:
    post = normalize_post(item, kind)
    title = post["title"] or str(item.get("repo") or "")
    url = canonical_url(item.get("reddit_url") or item.get("hn_url") or post["url"])
    summary = clean_text(post["summary"] or item.get("description") or "")[:config.max_document_chars]
    published = item.get("published_at") or ""
    if item.get("created_utc"):
        published = datetime.fromtimestamp(float(item["created_utc"]), timezone.utc).isoformat()
    repo = str(item.get("repo") or "")
    signal = Signal(stable_id("sig", post["source"], url), post["source"], kind, title, url, summary,
                    str(item.get("author") or ""), published,
                    {"score": post["score"], "comments": post["num_comments"]},
                    {"name": repo, "stars": None, "open_issues": None, "last_updated": None, "archived": None},
                    item)
    signal.documents = [document(signal, title + "\n" + summary)]
    linked = item.get("url")
    if linked and canonical_url(linked) != url:
        signal.related_urls = [canonical_url(linked)]
    return signal


def enrich_signal(signal: Signal, config: ProjectConfig) -> Signal:
    if not config.max_comments:
        return signal
    if signal.source == "hackernews":
        item_id = parse_qs(urlsplit(signal.url).query).get("id", [""])[0]
        if not item_id.isdigit():
            return signal
        response = http_get(f"https://hn.algolia.com/api/v1/items/{item_id}", timeout=20)
        response.raise_for_status()
        tree = response.json()
        # ponytail: bound to top-level comments; deeper traversal can follow demonstrated coverage gaps.
        entries = [tree] + list(islice(tree.get("children", []), config.max_comments))
        for entry in entries:
            text = clean_text(entry.get("text") or "")[:config.max_document_chars]
            if text:
                signal.documents.append(document(signal, text,
                    "https://news.ycombinator.com/item?id=" + str(entry["id"]), entry.get("author") or ""))
    elif signal.source.startswith("reddit_"):
        response = http_get(signal.url.rstrip("/") + ".json",
                            params={"limit": config.max_comments, "depth": 1},
                            headers={"User-Agent": "AutoResearch Project Research"}, timeout=20)
        response.raise_for_status()
        listings = response.json()
        for child in listings[1]["data"]["children"][:config.max_comments]:
            item = child.get("data", {})
            text = item.get("body") or ""
            if text and text not in ("[deleted]", "[removed]"):
                signal.documents.append(document(signal, text[:config.max_document_chars],
                                                  signal.url, item.get("author") or ""))
    return signal


def project_channels(config: ProjectConfig) -> list[channels.Channel]:
    result = []
    queries = ([config.topic] if config.topic else []) + config.queries
    for channel in channels.collection_channels():
        source = "github" if channel.key == "github_trending" else channel.key
        group = channel.kind if channel.kind in ("academic", "media") else source
        if not getattr(config.sources, group, False):
            continue
        fetch = channel.fetch
        if source == "reddit":
            def fetch(module, window):
                return [post for sub in config.subreddits for query in queries
                        for post in module.search_reddit_research(sub, query, window.time_filter,
                                                                  strict=True, include_metadata=True)]
        elif source == "hackernews":
            def fetch(module, window):
                return module.get_hn_discussed(window.time_filter_days, queries=queries, min_comments=0,
                                              include_content=True, strict=True)
        elif source == "github":
            def fetch(module, window):
                return module.collect_trending(since=channels.GITHUB_SINCE.get(window.time_filter, "monthly"),
                                               keywords=None, strict=True)
        result.append(replace(channel, fetch=fetch, required=group in config.required_sources))
    return result


def collect_signals(config: ProjectConfig) -> list[Signal]:
    window_name = "week" if config.lookback_days <= 7 else "month" if config.lookback_days <= 30 else "year"
    window = channels.Window(window_name, config.lookback_days, config.lookback_days, config.lookback_days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.lookback_days)
    batches = []
    healthy = 0
    for channel in project_channels(config):
        try:
            parts = channels.collect(channel, window)
            items = [normalize_signal(item, channel.kind, config) for values in parts.values() for item in values]
            filtered = []
            for item in items:
                if item.published_at:
                    when = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=timezone.utc)
                    if when < cutoff:
                        continue
                filtered.append(item)
            batches.append(filtered)
            healthy += 1
            logging.info("[Collect] %s: %d signals", channel.key, len(filtered))
        except Exception as exc:
            if channel.required:
                raise RuntimeError(f"Required source {channel.key} failed: {exc}") from exc
            logging.warning("[Collect] %s failed: %s", channel.key, exc)
    if not healthy:
        raise RuntimeError("No source completed collection; check source configuration and network")
    unique, seen_url, seen_title = [], set(), set()
    # Round-robin prevents one prolific source from consuming the entire global signal budget.
    for row in zip_longest(*batches):
        for item in row:
            if item is None:
                continue
            title = normalize_title(item.title)
            if item.url in seen_url or (title and title in seen_title):
                continue
            seen_url.add(item.url)
            if title:
                seen_title.add(title)
            unique.append(item)
    selected = unique[:config.max_signals]
    for item in selected:
        try:
            enrich_signal(item, config)
        except Exception as exc:
            logging.warning("[Content] %s: %s", item.url, exc)
            item.raw_metadata["content_error"] = str(exc)
    return selected
