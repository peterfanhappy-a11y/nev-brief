"""端到端内容烟测（无 DB / 无邮件）：crawl → select → summarize → 渲染预览 HTML。

验证 DeepSeek 两阶段 prompt 真能产出结构化中文简报。
Run: uv run python packages/ai-brief/scripts/smoke_content.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date

# Windows 控制台默认 GBK，打印 emoji 会崩；强制 utf-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai_brief import composer, config
from ai_brief.crawler import runner as crawl_runner
from ai_brief.selector import select
from ai_brief.summarizer import summarize


async def main() -> None:
    config.CRAWL_MAX_ARTICLES_PER_SOURCE = 6
    config.CRAWL_MIN_INTERVAL_S = 0.3
    # 用几个确认可用的源做烟测
    srcs = [
        {"name": "OpenAI Blog", "type": "rss", "url": "https://openai.com/news/rss.xml",
         "locale": "en", "authority": 10, "enabled": True},
        {"name": "TechCrunch AI", "type": "rss",
         "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
         "locale": "en", "authority": 8, "enabled": True},
        {"name": "量子位", "type": "rss", "url": "https://www.qbitai.com/feed",
         "locale": "zh", "authority": 8, "enabled": True},
        {"name": "The Verge AI", "type": "rss",
         "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
         "locale": "en", "authority": 7, "enabled": True},
    ]
    print("=== crawl ===")
    articles = await crawl_runner.crawl_all(srcs)
    print(f"crawled {len(articles)} articles")

    # 转成 Candidate（模拟 DB fetch）
    from ai_brief.storage import Candidate
    cands = [
        Candidate(id=f"c{i}", source_name=a.source_name, locale=a.locale,
                  authority=a.authority, url=a.url, title=a.title,
                  content=a.content, og_image=a.og_image)
        for i, a in enumerate(articles)
    ]
    if not cands:
        print("NO CANDIDATES — 抓取全失败，无法继续")
        return

    print("\n=== select (Stage-1, real DeepSeek) ===")
    sel = await select(cands)
    if sel is None:
        print("SELECT FAILED")
        return
    print(f"featured ids: {sel.featured_ids()}")
    print(f"themes: {[(k, v['pick']) for k, v in sel.themes.items()]}")
    print(f"tools: {sel.tool_candidates}  quick_hits: {sel.quick_hits}")
    print(f"tip: {sel.daily_tip_topic}  dupes: {sel.dupe_group_count}")

    print("\n=== summarize (Stage-2, real DeepSeek) ===")
    brief = await summarize(sel, cands, brief_date=str(date.today()), yesterday_top=None)
    if brief is None:
        print("SUMMARIZE FAILED")
        return
    print(f"SUBJECT: {brief.subject}")
    print(f"PREHEADER: {brief.preheader}")
    print("INTRO:")
    for b in brief.intro_bullets:
        print(f"  {b}")
    print(f"FEATURED ({len(brief.featured)}):")
    for f in brief.featured:
        print(f"  [{f.theme_label}] {f.headline}")
        for d in f.details:
            print(f"      - {d}")
        print(f"      意义: {f.significance}")
        print(f"      {f.source_name} {f.url} img={'Y' if f.og_image else '-'}")
    print(f"TOOLS: {[(t.name, t.one_liner) for t in brief.tools]}")
    if brief.daily_tip:
        print(f"TIP: {brief.daily_tip.title} — {brief.daily_tip.body}")
    print(f"QUICK: {[q.text for q in brief.quick_hits]}")

    out = "logs/ai_preview.html"
    import os
    os.makedirs("logs", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(composer.render_preview(brief, date.today()))
    print(f"\n=== 预览 HTML 写入 {out} ===")


if __name__ == "__main__":
    asyncio.run(main())
