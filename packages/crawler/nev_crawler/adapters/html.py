"""HTML adapter — 列表页 CSS 选择器抓元数据（不抓全文）。

合规边界（spec §5.2.3）：仅抽 title / url / time / 摘要片段；不爬全文。
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin
from uuid import UUID

from selectolax.parser import HTMLParser

from nev_crawler.adapters.base import Adapter, FetchResult
from nev_crawler.http_client import make_client
from nev_shared.logger import get_logger
from python.content import ArticleRaw

log = get_logger("html")


class HTMLAdapter(Adapter):
    type_name = "html_scrape"

    async def fetch(self, source: dict[str, Any]) -> FetchResult:
        extra = source.get("extra") or {}
        required = ["list_selector", "title_selector", "link_selector", "link_attr"]
        missing = [k for k in required if k not in extra]
        if missing:
            return FetchResult(error=f"extra missing selectors: {missing}")

        url = source["url"]
        source_id = UUID(source["id"])
        try:
            async with make_client(user_agent=extra.get("user_agent")) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:  # noqa: BLE001
            log.warning("html_fetch_failed", source=source.get("name"), error=str(exc))
            return FetchResult(error=str(exc))

        articles: list[ArticleRaw] = []
        tree = HTMLParser(html)
        for li in tree.css(extra["list_selector"]):
            title_node = li.css_first(extra["title_selector"])
            link_node = li.css_first(extra["link_selector"])
            if not title_node or not link_node:
                continue
            href = (link_node.attributes.get(extra["link_attr"]) or "").strip()
            if not href:
                continue
            article_url = urljoin(url, href)
            articles.append(ArticleRaw(
                source_id=source_id,
                url=article_url,
                title=title_node.text(strip=True),
            ))
        log.info("html_fetched", source=source.get("name"), count=len(articles))
        return FetchResult(articles=articles)
