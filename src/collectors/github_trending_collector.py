"""GitHub Trending 采集器 - 白色，HTML 解析"""

from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from api_retry import http_get  # noqa: E402

AI_KEYWORDS = [
    "llm", "gpt", "transformer", "diffusion", "attention",
    "multimodal", "agent", "rag", "fine-tune", "finetune",
    "reasoning", "inference", "neural", "deep-learning",
    "machine-learning", "ai", "nlp", "cv", "reinforcement",
    "world-model", "embodied", "language-model",
]


def collect_trending(since="daily", *, keywords=AI_KEYWORDS, strict=False):
    """采集 GitHub Trending ML/AI 相关项目"""
    repos = []
    url = f"https://github.com/trending?since={since}"
    headers = {"User-Agent": "Mozilla/5.0 IdeaProbe/0.1"}

    try:
        resp = http_get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            if strict:
                resp.raise_for_status()
            print(f"  [GitHub] HTTP {resp.status_code}")
            return repos

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.find_all("article", class_="Box-row")

        for article in articles:
            h2 = article.find("h2")
            if not h2:
                continue
            a_tag = h2.find("a")
            if not a_tag:
                continue

            repo_path = a_tag.get("href", "").strip("/")
            repo_name = repo_path.split("/")[-1].lower() if "/" in repo_path else ""
            description_p = article.find("p")
            description = description_p.get_text(strip=True) if description_p else ""

            stars_span = article.find("span", class_="d-inline-block float-sm-right")
            stars_today = ""
            if stars_span:
                stars_today = stars_span.get_text(strip=True)

            full_text = (repo_name + " " + description).lower()
            is_ai = keywords is None or any(kw in full_text for kw in keywords)
            if not is_ai:
                continue

            repos.append({
                "source": "github_trending",
                "source_category": "engineering",
                "repo": repo_path,
                "url": f"https://github.com/{repo_path}",
                "description": description,
                "stars_today": stars_today,
                "since": since,
                "collected_at": datetime.now().isoformat(),
            })

        print(f"  [GitHub] Trending ({since}): 扫描 {len(articles)} 项目，AI 相关 {len(repos)} 个")
    except Exception as e:
        if strict:
            raise
        print(f"  [GitHub] 失败: {e}")

    return repos
