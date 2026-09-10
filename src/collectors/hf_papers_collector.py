"""HuggingFace Daily Papers 采集器 - 白色，官方 JSON API"""

from datetime import datetime, timedelta
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from api_retry import http_get  # noqa: E402
from config.settings import HF_PAPERS_API


def collect_daily_papers(date=None, days_back=3):
    """采集HuggingFace Daily Papers"""
    all_papers = []

    for i in range(days_back):
        target_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"{HF_PAPERS_API}?date={target_date}"

        try:
            resp = http_get(url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    paper = item.get("paper", {})
                    all_papers.append({
                        "source": "hf_daily_papers",
                        "source_category": "academic",
                        "title": paper.get("title", ""),
                        "abstract": paper.get("summary", ""),
                        "authors": [a.get("name", "") for a in paper.get("authors", [])[:5]],
                        "arxiv_id": paper.get("id", ""),
                        "upvotes": paper.get("upvotes", 0),
                        "num_comments": paper.get("numComments", 0),
                        "published": paper.get("publishedAt", ""),
                        "submitted_by": item.get("submittedBy", {}).get("fullname", ""),
                        "url": f"https://huggingface.co/papers/{paper.get('id', '')}",
                        "github_repo": paper.get("githubRepo", ""),
                        "github_stars": paper.get("githubStars", 0),
                        "date": target_date,
                        "collected_at": datetime.now().isoformat(),
                    })
                print(f"  [HF Papers] {target_date}: {len(data)} 篇")
            else:
                print(f"  [HF Papers] {target_date}: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [HF Papers] {target_date} 失败: {e}")

    return all_papers
