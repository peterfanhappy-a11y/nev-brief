"""Crawler runner — 编排 sources × adapters，单源失败不影响其他源。"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from nev_crawler.adapters.api import APIAdapter
from nev_crawler.adapters.base import Adapter, FetchResult
from nev_crawler.adapters.html import HTMLAdapter
from nev_crawler.adapters.nextjs_json import NextJSJSONAdapter
from nev_crawler.adapters.rss import RSSAdapter
from nev_crawler.adapters.rsshub import RSSHubAdapter
from nev_crawler.rate_limiter import DomainRateLimiter
from nev_crawler.robots import RobotsChecker
from nev_shared.logger import get_logger

log = get_logger("runner")

DEFAULT_REGISTRY: dict[str, Adapter] = {
    "rss": RSSAdapter(),
    "html_scrape": HTMLAdapter(),
    "api": APIAdapter(),
    "rsshub": RSSHubAdapter(),
    "nextjs_json": NextJSJSONAdapter(),
}


async def crawl_sources(
    sources: list[dict[str, Any]],
    adapter_registry: dict[str, Adapter] | None = None,
    rate_limiter: DomainRateLimiter | None = None,
    robots: RobotsChecker | None = None,
) -> list[dict[str, Any]]:
    """对每个 source 并行调用对应 adapter。返回每个源的执行报告。"""
    registry = adapter_registry or DEFAULT_REGISTRY
    limiter = rate_limiter or DomainRateLimiter()
    robots_check = robots or RobotsChecker()

    enabled = [s for s in sources if s.get("enabled", True)]
    tasks = [_crawl_one(s, registry, limiter, robots_check) for s in enabled]
    return await asyncio.gather(*tasks)


async def _crawl_one(
    source: dict[str, Any],
    registry: dict[str, Adapter],
    limiter: DomainRateLimiter,
    robots: RobotsChecker,
) -> dict[str, Any]:
    name = source.get("name", "?")
    started = datetime.utcnow()
    try:
        adapter = registry.get(source["type"])
        if not adapter:
            return _report(name, started, False, error=f"no adapter for type={source['type']}")

        url = source["url"]
        # robots.txt 检查（RSSHub 自身免，其他类型都检查）
        if source["type"] != "rsshub":
            allowed = await robots.is_allowed(url)
            if not allowed:
                log.warning("robots_disallowed", source=name, url=url)
                return _report(name, started, False, error="robots.txt disallows")

        domain = urlparse(url).netloc or "rsshub"
        await limiter.acquire(domain)

        result: FetchResult = await adapter.fetch(source)
        return _report(
            name, started, result.ok,
            articles=len(result.articles), error=result.error,
            raw_articles=result.articles,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("crawl_one_exception", source=name, error=str(exc))
        return _report(name, started, False, error=str(exc))


def _report(
    name: str, started: datetime, ok: bool,
    articles: int = 0, error: str | None = None,
    raw_articles: list | None = None,
) -> dict[str, Any]:
    return {
        "source_name": name,
        "ok": ok,
        "articles": articles,
        "error": error,
        "raw_articles": raw_articles or [],
        "started_at": started.isoformat(),
        "finished_at": datetime.utcnow().isoformat(),
    }
