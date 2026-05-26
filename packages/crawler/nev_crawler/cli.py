"""nev_crawler CLI — python -m nev_crawler run [--window 24h] [--type all]"""
from __future__ import annotations

import argparse
import asyncio
import sys

import psycopg

from nev_crawler.runner import crawl_sources
from nev_shared.config import get_settings
from nev_shared.logger import configure_logging, get_logger

log = get_logger("crawler.cli")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m nev_crawler")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="拉取所有启用信源")
    run.add_argument("--window", default="24h", help="时间窗（仅记录到日志，过滤在 pipeline 做）")
    run.add_argument("--type", default="all",
                     choices=["domestic", "overseas", "official", "all"],
                     help="按 locale/category 过滤源")
    return p


def _load_sources(conn: psycopg.Connection, type_filter: str) -> list[dict]:
    where = "enabled = true"
    if type_filter == "domestic":
        where += " AND locale = 'zh'"
    elif type_filter == "overseas":
        where += " AND locale = 'en'"
    elif type_filter == "official":
        where += " AND category IN ('official','association','oem')"

    with conn.cursor() as cur:
        cur.execute(f"SELECT id, name, type, url, locale, category, enabled FROM sources WHERE {where}")
        cols = [c.name for c in cur.description]
        rows = cur.fetchall()
    sources = []
    for r in rows:
        s = dict(zip(cols, r, strict=True))
        s["id"] = str(s["id"])
        s["extra"] = {}  # 从 DB 读不到 extra；HTML 类型暂用 YAML 配置
        sources.append(s)
    return sources


async def _async_main(args: argparse.Namespace) -> int:
    try:
        configure_logging(level=get_settings().log_level)
    except Exception:  # noqa: BLE001
        # Settings 未配置时（如纯 --help 调用），跳过日志配置
        configure_logging(level="INFO")
    db_url = "postgresql://nev:nev_local_dev@localhost:54322/nev_brief"  # MVP 本地；生产用 Supabase
    conn = psycopg.connect(db_url)
    try:
        sources = _load_sources(conn, args.type)
        log.info("loaded_sources", count=len(sources), type_filter=args.type)
        reports = await crawl_sources(sources)
        ok = sum(1 for r in reports if r["ok"])
        total_articles = sum(r["articles"] for r in reports)
        log.info("crawl_done", ok=ok, total=len(reports), articles=total_articles)
        print(f"OK {ok}/{len(reports)} sources, {total_articles} articles fetched.")
        return 0 if ok > 0 else 1
    finally:
        conn.close()


def main() -> int:
    args = _build_parser().parse_args()
    if args.cmd == "run":
        return asyncio.run(_async_main(args))
    return 2


if __name__ == "__main__":
    sys.exit(main())
