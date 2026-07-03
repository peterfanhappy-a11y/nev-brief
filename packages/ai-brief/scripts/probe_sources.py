"""One-shot probe: check candidate AI feed/list URLs for reachability + parseability.

Run: uv run python packages/ai-brief/scripts/probe_sources.py
Reports per URL: HTTP status, feedparser entry count (for RSS), first entry title.
Network failures here may be Clash-specific — the real crawl runs on Mac mini.
"""
from __future__ import annotations

import asyncio

import feedparser
import httpx

CANDIDATES = [
    ("OpenAI Blog", "rss", "https://openai.com/news/rss.xml", "en"),
    ("Anthropic News", "html", "https://www.anthropic.com/news", "en"),
    ("Google DeepMind Blog", "rss", "https://deepmind.google/blog/rss.xml", "en"),
    ("TechCrunch AI", "rss", "https://techcrunch.com/category/artificial-intelligence/feed/", "en"),
    ("VentureBeat AI", "rss", "https://venturebeat.com/category/ai/feed/", "en"),
    ("The Verge AI", "rss", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "en"),
    ("Hugging Face Blog", "rss", "https://huggingface.co/blog/feed.xml", "en"),
    ("MIT Tech Review AI", "rss", "https://www.technologyreview.com/topic/artificial-intelligence/feed", "en"),
    ("机器之心", "rss", "https://www.jiqizhixin.com/rss", "zh"),
    ("量子位", "rss", "https://www.qbitai.com/feed", "zh"),
    ("36kr AI", "html", "https://36kr.com/information/AI/", "zh"),
    ("虎嗅", "rss", "https://www.huxiu.com/rss/0.xml", "zh"),
    ("InfoQ 中文", "rss", "https://www.infoq.cn/feed", "zh"),
    ("新智元(微信-rsshub)", "rss", "https://rsshub.app/wechat/ce/xinzhiyuan", "zh"),
]

UA = "AIVIZENS-Bot/1.0 (+https://aivizens.com/about)"


async def probe(client: httpx.AsyncClient, name: str, kind: str, url: str) -> str:
    try:
        r = await client.get(url, headers={"User-Agent": UA}, timeout=20.0)
    except Exception as e:  # noqa: BLE001
        return f"  [{kind:4}] {name:24} FAIL  {type(e).__name__}: {str(e)[:60]}"
    status = r.status_code
    note = ""
    if kind == "rss" and status == 200:
        fp = feedparser.parse(r.content)
        n = len(fp.entries)
        first = fp.entries[0].title[:40] if n else "(no entries)"
        note = f"entries={n:3}  first={first!r}"
    elif kind == "html" and status == 200:
        note = f"html {len(r.text)//1024}KB"
    return f"  [{kind:4}] {name:24} {status}  {note}"


async def main() -> None:
    async with httpx.AsyncClient(follow_redirects=True, trust_env=False) as client:
        results = await asyncio.gather(
            *(probe(client, n, k, u) for n, k, u, _ in CANDIDATES)
        )
    print("\n".join(results))


if __name__ == "__main__":
    asyncio.run(main())
