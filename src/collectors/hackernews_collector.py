"""Search Hacker News discussions through the Algolia API."""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api_retry import http_get  # noqa: E402


def get_hn_discussed(time_filter_days=30, *, queries=None, min_comments=20, include_content=False, strict=False):
    """从 HN Algolia API 获取近 N 天内 AI 高讨论帖"""
    cutoff_ts = int(time.time()) - time_filter_days * 86400
    queries = queries if queries is not None else [
        "LLM",
        "machine learning",
        "neural network",
        "AI research",
        "language model",
        "diffusion",
        "reasoning",
    ]
    seen_ids = set()
    results = []

    for q in queries:
        try:
            params = {
                "query": q,
                "tags": "story",
                "numericFilters": f"num_comments>{min_comments},created_at_i>{cutoff_ts}",
                "hitsPerPage": 30,
            }
            resp = http_get(
                "https://hn.algolia.com/api/v1/search",
                params=params,
                timeout=20,
            )
            if resp.status_code != 200:
                if strict:
                    resp.raise_for_status()
                continue
            hits = resp.json().get("hits", [])
            for hit in hits:
                hn_id = hit.get("objectID", "")
                if hn_id in seen_ids:
                    continue
                seen_ids.add(hn_id)
                results.append({
                    "source": "hackernews",
                    "title": hit.get("title", "").strip(),
                    "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hn_id}",
                    "hn_url": f"https://news.ycombinator.com/item?id={hn_id}",
                    "score": hit.get("points", 0) or 0,
                    "num_comments": hit.get("num_comments", 0) or 0,
                    "summary": "",
                })
                if include_content:
                    results[-1].update(summary=hit.get("story_text") or "",
                                       author=hit.get("author") or "",
                                       published_at=hit.get("created_at") or "")
        except Exception as e:
            if strict:
                raise
            print(f"  [HN/{q}] 失败: {e}")
            continue

    return results
