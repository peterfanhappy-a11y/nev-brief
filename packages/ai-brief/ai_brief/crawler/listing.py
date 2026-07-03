"""HTML 列表页解析 — 用 CSS 选择器提取文章 URL。

用于无 RSS 的源（Anthropic、36kr）。只出 URL（+ 尽力取锚文本作标题兜底），
正文由 runner 抓文章页补齐。相对 URL 用 base 补全。
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from selectolax.parser import HTMLParser


@dataclass(frozen=True)
class ListingLink:
    url: str
    title: str | None


def parse_listing(
    html: str,
    *,
    base_url: str,
    link_selector: str,
    link_attr: str = "href",
) -> list[ListingLink]:
    tree = HTMLParser(html)
    out: list[ListingLink] = []
    seen: set[str] = set()
    for node in tree.css(link_selector):
        href = (node.attributes.get(link_attr) or "").strip()
        if not href:
            continue
        url = urljoin(base_url, href)
        if not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        anchor = node.text(strip=True) or None
        out.append(ListingLink(url=url, title=anchor))
    return out
