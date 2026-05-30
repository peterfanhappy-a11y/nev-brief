"""从主页提取导航链接，帮助找到正确的新闻/数据栏目 URL。

用法: uv run python debug_nav.py
"""
from __future__ import annotations

import asyncio
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

SITES = [
    ("中汽协 CAAM",   "http://www.caam.org.cn/",     ["产销", "新能源", "数据", "统计", "动态", "新闻", "信息"]),
    ("乘联会 CPCA",   "https://www.cpcaauto.com/",   ["周度", "销量", "市场", "新能源", "数据", "报告", "周报", "月报"]),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


async def discover_nav(name: str, url: str, keywords: list[str]) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {name}")
    print(f"  Homepage: {url}")
    print("=" * 70)
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            print(f"  HTTP {resp.status_code}  (final: {resp.url})")
            if resp.status_code >= 400:
                return
            tree = HTMLParser(resp.text)

            # 1. 拿所有链接（文本 + href）
            all_links = []
            for a in tree.css("a[href]"):
                text = a.text(strip=True)
                href = a.attributes.get("href", "")
                if not text or not href or href.startswith(("#", "javascript:")):
                    continue
                abs_url = urljoin(str(resp.url), href)
                all_links.append((text, abs_url))

            # 2. 按关键词过滤（新闻/数据相关）
            matched = []
            for text, link in all_links:
                if any(kw in text for kw in keywords):
                    matched.append((text, link))

            print(f"\n  匹配关键词的链接 ({len(matched)} 条):")
            seen_urls: set[str] = set()
            for text, link in matched:
                if link in seen_urls:
                    continue
                seen_urls.add(link)
                print(f"    [{text[:30]:<30s}] {link}")

            # 3. 顺便列出导航栏（通常 li.mainlevel 等）
            print(f"\n  顶部导航候选（li.mainlevel / nav 等）:")
            nav_selectors = ["li.mainlevel a", "nav a", ".nav a", "#nav a", ".menu a", "ul.menu li a"]
            for sel in nav_selectors:
                nodes = tree.css(sel)
                if 3 <= len(nodes) <= 20:
                    print(f"    [via {sel}]")
                    for n in nodes:
                        text = n.text(strip=True)
                        href = n.attributes.get("href", "")
                        if text and href and not href.startswith(("#", "javascript:")):
                            print(f"      {text[:30]:<30s}  {urljoin(str(resp.url), href)}")
                    break
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")


async def main() -> None:
    for name, url, kw in SITES:
        await discover_nav(name, url, kw)
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
