"""Normalize community, academic and media collector records for IdeaProbe."""

import re


def normalize_post(item, source_type="community"):
    """将各采集器输出统一为 pipeline 内部格式: title, url, num_comments, score, summary, source, source_type
source_type: 'community' | 'academic' | 'media'"""
    title = item.get("title", "").strip()
    url = item.get("url") or item.get("reddit_url") or item.get("pdf_url") or item.get("hn_url") or ""
    url = url.strip() if url else ""
    summary = item.get("summary") or item.get("abstract") or item.get("selftext") or ""
    summary = summary.strip() if summary else ""
    source = item.get("source", "unknown")

    try:
        num_comments = int(item.get("num_comments", 0) or 0)
    except (ValueError, TypeError):
        num_comments = 0

    try:
        score = int(item.get("score", 0) or 0)
    except (ValueError, TypeError):
        score = 0

    normalized = {
        "title": title,
        "url": url,
        "num_comments": num_comments,
        "score": score,
        "summary": summary,
        "source": source,
        "source_type": source_type,
    }

    # Carry over any extra fields that may be useful downstream
    for k, v in item.items():
        if k not in normalized:
            normalized[k] = v

    return normalized


def normalize_title(t):
    """归一化 title 用于模糊匹配：去掉常见前缀/标点/空白，统一小写，保留前 60 字符"""
    if not t:
        return ""
    # Strip common Reddit/HN prefixes
    t = re.sub(r'^\[(P|D|R|N|Q|L|Research|Discussion|Project|News)\]\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'^(Ask HN|Show HN|Tell HN)\s*:\s*', '', t, flags=re.IGNORECASE)
    # Remove punctuation/whitespace noise
    t = re.sub(r'[\s\-_/\(\)\[\]\.,\'":;!?]+', ' ', t)
    t = t.strip().lower()
    return t[:60]
