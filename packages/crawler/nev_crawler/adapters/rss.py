"""RSS adapter — feedparser + httpx 拉取。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import feedparser

from nev_crawler.adapters.base import Adapter, FetchResult
from nev_crawler.http_client import make_client
from nev_shared.logger import get_logger
from python.content import ArticleRaw

log = get_logger("rss")


class RSSAdapter(Adapter):
    type_name = "rss"

    async def fetch(self, source: dict[str, Any]) -> FetchResult:
        url = source["url"]
        source_id = UUID(source["id"])
        try:
            async with make_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                feed = feedparser.parse(resp.content)
        except Exception as exc:  # noqa: BLE001
            log.warning("rss_fetch_failed", source=source.get("name"), error=str(exc))
            return FetchResult(error=str(exc))

        articles: list[ArticleRaw] = []
        for entry in feed.entries:
            article = ArticleRaw(
                source_id=source_id,
                url=entry.get("link", ""),
                title=entry.get("title"),
                content=entry.get("summary") or entry.get("description"),
                published_at=_parse_pubdate(entry),
            )
            if article.url:
                articles.append(article)
        log.info("rss_fetched", source=source.get("name"), count=len(articles))
        return FetchResult(articles=articles)


def _parse_pubdate(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
