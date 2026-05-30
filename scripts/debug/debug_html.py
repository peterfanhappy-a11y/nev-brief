"""调试 HTML adapter 的 selector — 跑这个看每个源页面 DOM 的真实结构。

用法: uv run python debug_html.py
"""
from __future__ import annotations

import asyncio
from collections import Counter

import httpx
from selectolax.parser import HTMLParser

# 5 个 count=0 的 HTML 源 + 1 个 404 的（探测新 URL）
SOURCES = [
    # 待发现 selector 的新 URL
    ("中汽协-行业动态",  "http://www.caam.org.cn/chn/8/cate_82/list_1.html",            ""),
    ("中汽协-产销数据",  "http://www.caam.org.cn/chn/5/cate_39/list_1.html",            ""),
    ("乘联会-周度",      "https://www.cpcaauto.com/news.php?types=csjd",                ""),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def analyze_dom(html: str, configured_selector: str) -> dict:
    """看每个候选 list_selector 命中多少元素，给出推荐。"""
    tree = HTMLParser(html)

    out: dict = {}

    # 1. 当前 selector 命中数
    if configured_selector:
        out["current"] = (configured_selector, len(tree.css(configured_selector)))

    # 2. 高频含链接的容器（按 class）
    link_parents: Counter = Counter()
    for a in tree.css("a[href]"):
        # 找最近的 class 不为空的祖先
        node = a.parent
        depth = 0
        while node and depth < 5:
            cls = (node.attributes.get("class") or "").strip()
            if cls:
                # 取第一个 class 词作为标识
                key = f"{node.tag}.{cls.split()[0]}"
                link_parents[key] += 1
                break
            node = node.parent
            depth += 1

    out["top_link_containers"] = link_parents.most_common(15)

    # 3. 常见列表标签：ul.xxx li / div.list / article 等的命中数
    candidates = [
        "article",
        "ul li a",
        ".list li",
        ".news-list li",
        ".article-list li",
        ".content-list li",
        "[class*='list'] li",
        "[class*='item']",
        "[class*='news']",
        "[class*='article']",
    ]
    candidate_hits = []
    for sel in candidates:
        try:
            n = len(tree.css(sel))
            if 5 <= n <= 100:
                candidate_hits.append((sel, n))
        except Exception:
            pass
    out["candidate_selectors"] = candidate_hits

    # 4. 页面 title （确认拿到的是新闻页而非反爬中间页）
    title_node = tree.css_first("title")
    out["page_title"] = title_node.text(strip=True) if title_node else "(no <title>)"

    return out


async def fetch_and_analyze(name: str, url: str, sel: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {name}")
    print(f"  URL: {url}")
    print(f"  Configured: {sel or '(none — discovery mode)'}")
    print("=" * 70)
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            print(f"  HTTP {resp.status_code}  (final URL: {resp.url})")
            print(f"  Body: {len(resp.text)} chars")
            if resp.status_code >= 400:
                return
            info = analyze_dom(resp.text, sel)
            print(f"  Page <title>: {info['page_title']}")
            if "current" in info:
                cur_sel, cur_n = info["current"]
                marker = "✅" if cur_n > 0 else "❌"
                print(f"  Current selector hits: {marker} {cur_n}")
            print("\n  Top link containers (by parent.class):")
            for k, v in info["top_link_containers"][:10]:
                print(f"    {v:>3d}x  {k}")
            print("\n  Candidate selectors (5-100 matches):")
            for k, v in info["candidate_selectors"]:
                print(f"    {v:>3d}x  {k}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")


async def main() -> None:
    for name, url, sel in SOURCES:
        await fetch_and_analyze(name, url, sel)
        await asyncio.sleep(1)  # 礼貌延迟


if __name__ == "__main__":
    asyncio.run(main())
