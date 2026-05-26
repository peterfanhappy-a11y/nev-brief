"""RSSHub adapter — 复用 RSS 解析，URL 拼接本地 RSSHub base。

spec §5.2.4: 本地 docker-compose RSSHub 在 localhost:1200。
"""
from __future__ import annotations

import os
from typing import Any

from nev_crawler.adapters.base import FetchResult
from nev_crawler.adapters.rss import RSSAdapter


class RSSHubAdapter(RSSAdapter):
    type_name = "rsshub"

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.environ.get("RSSHUB_BASE_URL", "http://localhost:1200")).rstrip("/")

    async def fetch(self, source: dict[str, Any]) -> FetchResult:
        path = source["url"]
        if not path.startswith("/"):
            path = "/" + path
        absolute = self.base_url + path
        modified = dict(source)
        modified["url"] = absolute
        return await super().fetch(modified)
