"""API adapter — 通用 JSON GET，路径 + 字段名可配置。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from nev_crawler.adapters.base import Adapter, FetchResult
from nev_crawler.http_client import make_client
from nev_shared.logger import get_logger
from python.content import ArticleRaw

log = get_logger("api")


class APIAdapter(Adapter):
    type_name = "api"

    async def fetch(self, source: dict[str, Any]) -> FetchResult:
        extra = source.get("extra") or {}
        items_path = extra.get("items_path", "items")
        title_f = extra.get("title_field", "title")
        url_f = extra.get("url_field", "url")
        pub_f = extra.get("published_field", "publishedAt")

        try:
            async with make_client() as client:
                resp = await client.get(source["url"])
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("api_fetch_failed", source=source.get("name"), error=str(exc))
            return FetchResult(error=str(exc))

        items = data.get(items_path, []) if isinstance(data, dict) else data
        source_id = UUID(source["id"])
        articles: list[ArticleRaw] = []
        for item in items:
            if not (item.get(url_f) and item.get(title_f)):
                continue
            articles.append(ArticleRaw(
                source_id=source_id,
                url=item[url_f],
                title=item[title_f],
                published_at=_parse_iso(item.get(pub_f)),
            ))
        log.info("api_fetched", source=source.get("name"), count=len(articles))
        return FetchResult(articles=articles)


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
