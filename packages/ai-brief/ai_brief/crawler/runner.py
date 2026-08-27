"""Crawl runner — 遍历 sources.yaml，抓 feed/listing → 逐篇抓文章页 → AiArticle 列表。

合规：robots.txt 检查（复用 nev_crawler.robots.RobotsChecker）、每源逐篇限速、
UA 标识、单篇失败跳过不炸全局。httpx trust_env=False 避免走 Clash SOCKS 代理。
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
import yaml
from nev_crawler.robots import RobotsChecker
from nev_shared.logger import get_logger

from ai_brief import config
from ai_brief.crawler import article as article_parser
from ai_brief.crawler.feeds import parse_feed
from ai_brief.crawler.listing import parse_listing
from ai_brief.storage import AiArticle

log = get_logger("ai_brief.crawl")

Source = dict[str, Any]


def load_sources(path: str | Path = config.SOURCES_YAML) -> list[Source]:
    with open(path, encoding="utf-8") as f:
        data = cast(dict[str, list[Source]], yaml.safe_load(f))
    return [s for s in data.get("sources", []) if s.get("enabled", False)]


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": config.CRAWL_USER_AGENT},
        timeout=httpx.Timeout(config.CRAWL_TIMEOUT_S, connect=10.0),
        follow_redirects=True,
        trust_env=False,   # 不走 Clash / SOCKS 代理
        http2=True,
    )


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await client.get(url)
        if r.status_code == 200:
            return r.text
        log.warning("ai_crawl.fetch_status", url=url, status=r.status_code)
    except Exception as e:  # noqa: BLE001
        log.warning("ai_crawl.fetch_failed", url=url, error=str(e)[:120])
    return None


@dataclass(frozen=True)
class _Seed:
    """一条待抓取条目 + feed 已提供的内容基线（文章页 403 时的兜底）。"""
    url: str
    title_hint: str | None
    published_at: str | None
    baseline_content: str | None  # RSS summary
    baseline_image: str | None    # RSS media/enclosure image


async def _collect_seeds(client: httpx.AsyncClient, source: Source) -> list[_Seed]:
    """RSS 用 feed（含 summary/image 基线），html_list 用选择器。"""
    stype = source["type"]
    url = source["url"]
    if stype == "rss":
        raw = await _fetch_text(client, url)
        if not raw:
            return []
        return [
            _Seed(e.url, e.title, e.published_at, e.summary, e.image)
            for e in parse_feed(raw)
        ]
    if stype == "html_list":
        raw = await _fetch_text(client, url)
        if not raw:
            return []
        extra = source.get("extra") or {}
        links = parse_listing(
            raw,
            base_url=url,
            link_selector=extra.get("link_selector", "a"),
            link_attr=extra.get("link_attr", "href"),
        )
        return [_Seed(link.url, link.title, None, None, None) for link in links]
    log.warning("ai_crawl.unknown_type", type=stype, source=source["name"])
    return []


async def crawl_source(
    client: httpx.AsyncClient,
    robots: RobotsChecker,
    source: Source,
) -> list[AiArticle]:
    name = source["name"]
    locale = source.get("locale", "en")
    authority = int(source.get("authority", 5))

    seeds = (await _collect_seeds(client, source))[: config.CRAWL_MAX_ARTICLES_PER_SOURCE]
    log.info("ai_crawl.source_entries", source=name, entries=len(seeds))

    articles: list[AiArticle] = []
    for s in seeds:
        # 内容基线来自 RSS（文章页反爬 403 时仍可用）
        title = s.title_hint
        content = s.baseline_content
        og_image = s.baseline_image

        allowed = True
        try:
            allowed = await robots.is_allowed(s.url)
        except Exception:  # noqa: BLE001 — robots 失败默认允许
            allowed = True

        if allowed:
            html = await _fetch_text(client, s.url)
            await asyncio.sleep(config.CRAWL_MIN_INTERVAL_S)  # 逐篇限速
            if html:
                parsed = article_parser.parse_article(html, fallback_title=s.title_hint)
                title = parsed["title"] or title
                # 文章页正文更长才升级，否则保留 RSS 基线
                if parsed["content"] and len(parsed["content"]) > len(content or ""):
                    content = parsed["content"]
                og_image = parsed["og_image"] or og_image
        else:
            log.info("ai_crawl.robots_disallow", url=s.url)

        if not title:
            continue
        articles.append(
            AiArticle(
                source_name=name,
                locale=locale,
                authority=authority,
                url=s.url,
                title=title,
                content=content,
                og_image=og_image,
                published_at=s.published_at,
            )
        )
    log.info("ai_crawl.source_done", source=name, articles=len(articles))
    return articles


async def crawl_all(
    sources: list[Source] | None = None,
    on_source: Callable[[list[AiArticle]], None] | None = None,
) -> list[AiArticle]:
    """抓取所有 enabled 源，返回全部 AiArticle。源之间串行（各自内部已限速）。

    on_source 若提供，每源抓完立即回调该源的 articles —— runner 用它增量 insert+commit，
    这样 10 分钟的抓取中途网络中断也不会丢已抓到的源。
    """
    srcs = sources if sources is not None else load_sources()
    robots = RobotsChecker(user_agent=config.CRAWL_USER_AGENT)
    out: list[AiArticle] = []
    async with _make_client() as client:
        for source in srcs:
            try:
                got = await crawl_source(client, robots, source)
                out.extend(got)
                if on_source is not None and got:
                    on_source(got)
            except Exception as e:  # noqa: BLE001 — 单源失败不炸全局
                log.error("ai_crawl.source_error", source=source.get("name"), error=str(e)[:160])
    log.info("ai_crawl.all_done", sources=len(srcs), articles=len(out))
    return out
