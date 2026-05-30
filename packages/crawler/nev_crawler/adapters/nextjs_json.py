"""Next.js __NEXT_DATA__ JSON adapter — 抓服务端嵌入的初始数据。

适用站点：动态 jsx-hash 类名让 CSS selector 不稳定，但 SSR HTML 里
有 <script id="__NEXT_DATA__"> 含完整初始数据 JSON。

extra 配置:
    json_path:        "props.pageProps.staticData.news"   — JSON 路径（点分）
    title_field:      "title"                              — 文章标题字段
    id_field:         "unique_id_str"                      — 文章 ID 字段
    url_template:     "https://www.dongchedi.com/article/{id}"  — URL 拼接模板
    published_field:  "publish_time"                       — Unix 时间戳字段（可选）
    content_field:    "abstract"                           — 摘要字段（可选）
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from selectolax.parser import HTMLParser

from nev_crawler.adapters.base import Adapter, FetchResult
from nev_crawler.http_client import make_client
from nev_shared.logger import get_logger
from python.content import ArticleRaw

log = get_logger("nextjs_json")


class NextJSJSONAdapter(Adapter):
    type_name = "nextjs_json"

    async def fetch(self, source: dict[str, Any]) -> FetchResult:
        extra = source.get("extra") or {}
        required = ["json_path", "title_field", "id_field", "url_template"]
        missing = [k for k in required if k not in extra]
        if missing:
            return FetchResult(error=f"extra missing: {missing}")

        url = source["url"]
        source_id = UUID(source["id"])
        try:
            async with make_client(user_agent=extra.get("user_agent")) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:  # noqa: BLE001
            log.warning("nextjs_fetch_failed", source=source.get("name"), error=str(exc))
            return FetchResult(error=str(exc))

        tree = HTMLParser(html)
        script = tree.css_first("script#__NEXT_DATA__")
        if not script:
            log.warning("nextjs_no_next_data", source=source.get("name"))
            return FetchResult(error="no __NEXT_DATA__ script tag")
        try:
            data = json.loads(script.text())
        except json.JSONDecodeError as e:
            log.warning("nextjs_json_parse_failed", source=source.get("name"), error=str(e))
            return FetchResult(error=f"json parse failed: {e}")

        # 按点分路径遍历 JSON
        items = data
        for key in extra["json_path"].split("."):
            if isinstance(items, dict):
                items = items.get(key)
            else:
                msg = f"json_path broken at '{key}', got {type(items).__name__}"
                log.warning("nextjs_path_broken", source=source.get("name"), error=msg)
                return FetchResult(error=msg)
            if items is None:
                msg = f"json_path key '{key}' not found"
                log.warning("nextjs_path_missing", source=source.get("name"), key=key)
                return FetchResult(error=msg)

        if not isinstance(items, list):
            msg = f"json_path target is {type(items).__name__}, expected list"
            log.warning("nextjs_not_a_list", source=source.get("name"), error=msg)
            return FetchResult(error=msg)

        articles: list[ArticleRaw] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            item_id = it.get(extra["id_field"])
            title = it.get(extra["title_field"])
            if not item_id or not title:
                continue
            article_url = extra["url_template"].format(id=item_id)

            published_at: datetime | None = None
            pf = extra.get("published_field")
            if pf and (ts := it.get(pf)) and isinstance(ts, (int, float)):
                try:
                    published_at = datetime.fromtimestamp(ts, tz=timezone.utc)
                except (ValueError, OSError):
                    published_at = None

            content: str | None = None
            cf = extra.get("content_field")
            if cf:
                content = it.get(cf)

            articles.append(ArticleRaw(
                source_id=source_id,
                url=article_url,
                title=str(title),
                content=content,
                published_at=published_at,
            ))
        log.info("nextjs_fetched", source=source.get("name"), count=len(articles))
        return FetchResult(articles=articles)
