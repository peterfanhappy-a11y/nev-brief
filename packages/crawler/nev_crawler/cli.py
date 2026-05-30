"""nev_crawler CLI — python -m nev_crawler run [--window 24h] [--type all]"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import psycopg
import yaml

from nev_crawler.runner import crawl_sources
from nev_crawler.storage import insert_articles_raw
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


def _load_extra_from_yaml() -> dict[str, dict]:
    """Load `extra` (HTML selectors etc.) from sources_seed.yaml, keyed by source name.

    sources 表暂无 extra 列；HTML adapter 需要的 selector 走 YAML 兜底直到 schema 迁移。
    """
    yaml_path = Path(__file__).parent / "sources_seed.yaml"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return {s["name"]: s.get("extra", {}) for s in data.get("sources", [])}


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
    extras = _load_extra_from_yaml()
    sources = []
    for r in rows:
        s = dict(zip(cols, r, strict=True))
        s["id"] = str(s["id"])
        s["extra"] = extras.get(s["name"], {})
        sources.append(s)
    return sources


async def _async_main(args: argparse.Namespace) -> int:
    try:
        settings = get_settings()
        configure_logging(level=settings.log_level)
        db_url = settings.database_url
    except Exception:  # noqa: BLE001
        # Settings 未配置时（如纯 --help 调用），跳过日志配置
        configure_logging(level="INFO")
        db_url = "postgresql://nev:nev_local_dev@localhost:54322/nev_brief"
    conn = psycopg.connect(db_url)
    try:
        sources = _load_sources(conn, args.type)
        log.info("loaded_sources", count=len(sources), type_filter=args.type)
        reports = await crawl_sources(sources)
        ok = sum(1 for r in reports if r["ok"])
        total_articles = sum(r["articles"] for r in reports)

        # Persist articles to DB
        total_inserted = 0
        for r in reports:
            raw_articles = r.get("raw_articles", [])
            if raw_articles:
                inserted = insert_articles_raw(conn, raw_articles)
                total_inserted += inserted
                conn.commit()

        log.info("crawl_done", ok=ok, total=len(reports), articles=total_articles, inserted=total_inserted)
        print(f"OK {ok}/{len(reports)} sources, {total_articles} fetched, {total_inserted} inserted to DB.")
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
