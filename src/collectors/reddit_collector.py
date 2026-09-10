"""Search public Reddit discussions for developer problems."""

import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from api_retry import http_get  # noqa: E402
from config.settings import REDDIT_USER_AGENT  # noqa: E402  路径插入之后才可导入


REDDIT_ORIGIN = "https://www.reddit.com"


def _reddit_thread_url(permalink):
    """Build a Reddit URL without allowing a relative value to replace its host."""
    if not isinstance(permalink, str):
        return REDDIT_ORIGIN
    if (
        not permalink.startswith("/")
        or permalink.startswith("//")
        or "\\" in permalink
        or any(ord(char) < 32 for char in permalink)
    ):
        return REDDIT_ORIGIN

    candidate = f"{REDDIT_ORIGIN}{permalink}"
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return REDDIT_ORIGIN
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.reddit.com"
        or parsed.username is not None
        or parsed.password is not None
    ):
        return REDDIT_ORIGIN
    return candidate


def _http_url(url):
    """Return a usable HTTP(S) URL, or an empty string for unsafe schemes."""
    if not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return url


def _is_reddit_self_url(url):
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return False
    return parsed.scheme == "https" and parsed.hostname == "www.reddit.com"


def search_reddit_research(subreddit, query, time_filter="month", limit=50, *, strict=False, include_metadata=False):
    """在 Reddit 搜索研究相关帖子（看近1个月）"""
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "sort": "relevance",
        "t": time_filter,
        "limit": limit,
        "restrict_sr": 1,
    }
    headers = {"User-Agent": REDDIT_USER_AGENT}
    results = []
    try:
        resp = http_get(url, params=params, headers=headers, timeout=20)
        if resp.status_code != 200:
            if strict:
                resp.raise_for_status()
            print(f"  [Reddit/{subreddit}] HTTP {resp.status_code}")
            return []
        data = resp.json()
        children = data.get("data", {}).get("children", [])
        for child in children:
            post = child.get("data", {})
            if not post:
                continue
            reddit_url = _reddit_thread_url(post.get("permalink", ""))
            external_url = _http_url(post.get("url", ""))
            # Prefer external link (paper) URL over reddit thread URL
            is_external = external_url and not _is_reddit_self_url(external_url)
            final_url = external_url if is_external else reddit_url
            results.append({
                "source": f"reddit_{subreddit.lower()}",
                "title": post.get("title", "").strip(),
                "url": final_url,
                "reddit_url": reddit_url,
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "summary": post.get("selftext") or "",
                "author": post.get("author", ""),
            })
            if include_metadata:
                results[-1]["created_utc"] = post.get("created_utc")
    except Exception as e:
        if strict:
            raise
        print(f"  [Reddit/{subreddit}] 失败: {e}")
    return results
