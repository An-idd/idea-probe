from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import channels
from project_research import signals
from project_research.config import ProjectConfig


def test_github_normalization_and_thread_identity():
    config = ProjectConfig()
    item = signals.normalize_signal({"repo": "org/tool", "description": "Tool description",
                                     "url": "https://github.com/org/tool", "source": "github_trending"},
                                    "community", config)
    assert item.title == "org/tool" and item.summary == "Tool description"
    assert item.repository["stars"] is None
    assert signals.thread_key("https://www.reddit.com/r/a/comments/abc/title/comment") == "reddit:abc"
    assert signals.thread_key("https://old.reddit.com/r/a/comments/abc/other") == "reddit:abc"
    assert signals.thread_key("https://news.ycombinator.com/item?id=123") == "hn:123"


def test_github_fetch_uses_standard_html_parser(monkeypatch):
    from collectors import github_trending_collector as github
    response = SimpleNamespace(status_code=200, text=(
        '<article class="Box-row"><h2><a href="/org/context">Context</a></h2>'
        '<p>Agent context history</p></article>'))
    monkeypatch.setattr(github, "http_get", lambda *a, **k: response)
    result = github.collect_trending(keywords=None, strict=True)
    assert len(result) == 1 and result[0]["repo"] == "org/context"


def test_collect_source_selection_and_failure(monkeypatch):
    config = ProjectConfig(max_comments=0)
    roster = signals.project_channels(config)
    assert {c.key for c in roster} == {"github_trending", "reddit", "hackernews"}
    assert not any(c.required for c in roster)
    monkeypatch.setattr(signals, "project_channels", lambda _: roster)
    def collect(channel, window):
        if channel.key == "reddit":
            raise RuntimeError("offline")
        return {"": [{"source": channel.key, "title": channel.key,
                       "url": f"https://example.org/{channel.key}"}]}
    monkeypatch.setattr(channels, "collect", collect)
    assert len(signals.collect_signals(config)) == 2
    monkeypatch.setattr(signals, "project_channels", lambda _: [replace(roster[0], key="reddit", required=True)])
    with pytest.raises(RuntimeError, match="Required source"):
        signals.collect_signals(config)


def test_failed_sources_are_not_empty_success(monkeypatch):
    monkeypatch.setattr(channels, "collect", lambda *a: (_ for _ in ()).throw(RuntimeError("offline")))
    with pytest.raises(RuntimeError, match="No source completed"):
        signals.collect_signals(ProjectConfig())


def test_custom_queries_and_subreddits():
    config = ProjectConfig(subreddits=["golang"], queries=["workaround"], topic="observability")
    calls = []
    reddit = next(c for c in signals.project_channels(config) if c.key == "reddit")
    module = SimpleNamespace(search_reddit_research=lambda *a, **kw: calls.append((a, kw)) or [])
    reddit.fetch(module, channels.Window())
    assert [a[0][0] for a in calls] == ["golang", "golang"]
    assert all(a[1]["strict"] for a in calls)


def test_reddit_uses_discussion_url_and_time_metadata():
    post = {"title": "Looking for replay", "source": "reddit_python", "url": "https://example.org/tool",
            "reddit_url": "https://www.reddit.com/r/python/comments/a/title/", "created_utc": 1760000000}
    item = signals.normalize_signal(post, "community", ProjectConfig())
    assert "reddit.com" in item.url and item.related_urls == ["https://example.org/tool"]
    assert datetime.fromisoformat(item.published_at).tzinfo == timezone.utc


def test_competitor_fetch_rejects_private_addresses(monkeypatch):
    from project_research import evidence
    monkeypatch.setattr(evidence.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="public addresses"):
        evidence.public_url("https://example.org/")


def test_competitor_redirect_is_revalidated(monkeypatch):
    from contextlib import contextmanager
    from project_research import evidence
    import httpx
    @contextmanager
    def stream(method, url, **kwargs):
        yield httpx.Response(302, headers={"location": "http://127.0.0.1/private"},
                             request=httpx.Request(method, url))
    def addresses(host, *args, **kwargs):
        return [(2, 1, 6, "", ("127.0.0.1" if host == "127.0.0.1" else "8.8.8.8", 443))]
    monkeypatch.setattr(evidence.httpx, "stream", stream)
    monkeypatch.setattr(evidence.socket, "getaddrinfo", addresses)
    with pytest.raises(ValueError, match="public addresses"):
        evidence.fetch_competitor("https://example.org/", None, ProjectConfig())


def test_competitor_content_has_a_size_limit(monkeypatch):
    from contextlib import contextmanager
    from project_research import evidence
    import httpx
    @contextmanager
    def stream(method, url, **kwargs):
        yield httpx.Response(200, content=b"x" * 1_000_001, request=httpx.Request(method, url))
    monkeypatch.setattr(evidence.httpx, "stream", stream)
    monkeypatch.setattr(evidence, "public_url", lambda url: url)
    with pytest.raises(ValueError, match="content limit"):
        evidence.fetch_competitor("https://example.org/", None, ProjectConfig())


def test_hn_body_and_comment_preserve_thread(monkeypatch):
    item = signals.normalize_signal({"title": "Ask HN: replay?", "url": "https://example.org/tool",
                                     "hn_url": "https://news.ycombinator.com/item?id=123",
                                     "source": "hackernews"}, "community", ProjectConfig())
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
        "id": 123, "text": "<p>How do I replay calls?</p>", "author": "one",
        "children": [{"id": 124, "text": "<p>I use a workaround.</p>", "author": "two"}]})
    monkeypatch.setattr(signals, "http_get", lambda *a, **k: response)
    signals.enrich_signal(item, ProjectConfig())
    assert len(item.documents) == 3
    assert {d.thread for d in item.documents} == {"hn:123"}
    assert item.documents[-1].url.endswith("id=124")


@pytest.mark.parametrize("oversized", [False, True])
def test_compressed_competitor_is_decoded_once_and_bounded(monkeypatch, oversized):
    import gzip
    from contextlib import contextmanager
    import httpx
    from project_research import evidence
    body = b"x" * 1_000_001 if oversized else b"<main>Context version history</main>"
    @contextmanager
    def stream(method, url, **kwargs):
        yield httpx.Response(200, headers={"content-encoding": "gzip", "content-type": "text/html"},
                             content=gzip.compress(body), request=httpx.Request(method, url))
    monkeypatch.setattr(evidence.httpx, "stream", stream)
    monkeypatch.setattr(evidence, "public_url", lambda url: url)
    idea = SimpleNamespace(source_signal_ids=["sig_test"])
    if oversized:
        with pytest.raises(ValueError, match="content limit"):
            evidence.fetch_competitor("https://example.org/", idea, ProjectConfig())
    else:
        result = evidence.fetch_competitor("https://example.org/", idea, ProjectConfig())
        assert result.text == "Context version history"
