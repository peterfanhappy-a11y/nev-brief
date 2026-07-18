"""ai_brief CLI — daily / crawl / select / compose / deliver。

用法：
  uv run python -m ai_brief daily [--date YYYY-MM-DD] [--dry-run] [--only-email X]
  uv run python -m ai_brief crawl
  uv run python -m ai_brief compose --date YYYY-MM-DD --preview-out out.html
  uv run python -m ai_brief deliver
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime

from nev_shared.config import get_settings
from nev_shared.logger import configure_logging

from ai_brief import composer, deliverer, storage
from ai_brief.crawler import runner as crawl_runner
from ai_brief.runner import connect, run_daily
from ai_brief.schema import AiBriefContent


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ai_brief", description="AIVIZENS AI 趋势每日简报")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("daily", help="全流程：crawl→select→summarize→compose→deliver")
    d.add_argument("--date", type=_parse_date, default=None)
    d.add_argument("--dry-run", action="store_true", help="停在 compose 前，只生成简报文档")
    d.add_argument("--only-email", default=None, help="只给该邮箱生成投递（测试用）")
    d.add_argument("--skip-crawl", action="store_true", help="跳过抓取，用已有 ai_articles")

    sub.add_parser("crawl", help="仅抓取，写 ai_articles")

    c = sub.add_parser("compose", help="仅渲染已生成的简报")
    c.add_argument("--date", type=_parse_date, default=None)
    c.add_argument("--only-email", default=None)
    c.add_argument("--preview-out", default=None, help="写一份预览 HTML 到文件，不落库")

    sub.add_parser("deliver", help="仅排空 pending 投递队列")
    return p


async def _cmd_daily(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        brief_date = args.date or datetime.now().date()
        r = await run_daily(
            conn, brief_date,
            only_email=args.only_email, dry_run=args.dry_run, skip_crawl=args.skip_crawl,
        )
        print(
            f"OK daily {r.brief_date} steps={'/'.join(r.steps)} "
            f"modules={r.modules} composed={r.composed} sent={r.sent} failed={r.failed}"
            + (f" ABORTED@{r.aborted_at}" if r.aborted_at else "")
        )
        return 1 if r.aborted_at else 0
    finally:
        conn.close()


async def _cmd_crawl(_args: argparse.Namespace) -> int:
    conn = connect()
    try:
        total_new = 0

        def _sink(articles) -> None:  # noqa: ANN001 — 每源增量落库
            nonlocal total_new
            total_new += storage.insert_articles(conn, articles)
            conn.commit()

        fetched = await crawl_runner.crawl_all(on_source=_sink)
        print(f"OK crawl fetched={len(fetched)} new={total_new}")
        return 0
    finally:
        conn.close()


def _cmd_compose(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        brief_date = args.date or datetime.now().date()
        if args.preview_out:
            raw = storage.fetch_brief(conn, brief_date)
            if raw is None:
                print(f"ERR no brief for {brief_date}")
                return 1
            html = composer.render_preview(AiBriefContent.model_validate(raw), brief_date)
            with open(args.preview_out, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"OK preview -> {args.preview_out}")
            return 0
        comp = composer.compose_for_date(conn, brief_date, only_email=args.only_email)
        conn.commit()
        print(f"OK compose {brief_date} composed={comp.get('composed', 0)}")
        return 0
    finally:
        conn.close()


def _cmd_deliver(_args: argparse.Namespace) -> int:
    conn = connect()
    try:
        res = deliverer.send_pending(conn)
        print(f"OK deliver attempted={res.attempted} sent={res.sent} failed={res.failed}")
        return 0
    finally:
        conn.close()


def main() -> int:
    configure_logging(level=get_settings().log_level)
    args = _build_parser().parse_args()
    if args.cmd == "daily":
        return asyncio.run(_cmd_daily(args))
    if args.cmd == "crawl":
        return asyncio.run(_cmd_crawl(args))
    if args.cmd == "compose":
        return _cmd_compose(args)
    if args.cmd == "deliver":
        return _cmd_deliver(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
