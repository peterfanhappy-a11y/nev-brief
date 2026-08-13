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
import json
import os
from datetime import date, datetime

from nev_shared.config import get_settings
from nev_shared.logger import configure_logging

from ai_brief import composer, deliverer, stats, storage
from ai_brief.crawler import runner as crawl_runner
from ai_brief.digest.gmail_input import GmailDigestAdapter
from ai_brief.preview_tokens import build_preview_url
from ai_brief.runner import (
    approve_brief,
    connect,
    generate_for_review,
    release_approved,
)
from ai_brief.schema import AiBriefContent


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ai_brief", description="AIVIZENS AI 趋势每日简报")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("daily", help="已停用：请使用 generate/approve/release/deliver")
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

    g = sub.add_parser("generate", help="生成候选简报并等待人工审核")
    g.add_argument("--date", type=_parse_date, required=True)

    v = sub.add_parser("preview-url", help="生成只读审核预览 URL")
    v.add_argument("--date", type=_parse_date, required=True)
    v.add_argument("--ttl-minutes", type=int, default=15)

    a = sub.add_parser("approve", help="批准候选简报")
    a.add_argument("--date", type=_parse_date, required=True)

    r = sub.add_parser("release", help="发布已批准简报并创建投递")
    r.add_argument("--date", type=_parse_date, required=True)
    r.add_argument("--only-email", default=None)

    d = sub.choices["deliver"]
    d.add_argument("--date", type=_parse_date, default=None)
    d.add_argument("--retry-transient", action="store_true")

    s = sub.add_parser("stats", help="输出隐私安全运营统计")
    s.add_argument("--date", type=_parse_date, default=None)
    s.add_argument("--json", action="store_true")
    return p


async def _cmd_daily(args: argparse.Namespace) -> int:
    del args
    print("ERR daily is retired; use generate, approve, release, and deliver", flush=True)
    return 2


async def _cmd_generate(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        result = await generate_for_review(conn, args.date, GmailDigestAdapter())
        print(
            json.dumps(
                {"date": result.brief_date, "status": result.status, "run_id": str(result.run_id)},
                ensure_ascii=False,
            )
        )
        return result.exit_code
    finally:
        conn.close()


def _cmd_preview_url(args: argparse.Namespace) -> int:
    if args.ttl_minutes <= 0 or args.ttl_minutes > 15:
        print("ERR ttl-minutes must be between 1 and 15")
        return 2
    expires = int(datetime.now().timestamp()) + args.ttl_minutes * 60
    try:
        print(
            build_preview_url(
                args.date.isoformat(),
                expires,
                secret=os.environ.get("PREVIEW_SIGNING_SECRET"),
            )
        )
        return 0
    except ValueError as exc:
        print(f"ERR {exc}")
        return 2


def _cmd_approve(args: argparse.Namespace) -> int:
    operator = os.environ.get("AIVIZENS_OPERATOR_ID", "").strip()
    if not operator:
        print("ERR AIVIZENS_OPERATOR_ID is required")
        return 2
    conn = connect()
    try:
        result = approve_brief(conn, args.date, approved_by=operator)
        print(
            json.dumps(
                {"date": result.brief_date, "status": result.status, "changed": result.changed},
                ensure_ascii=False,
            )
        )
        return result.exit_code
    finally:
        conn.close()


def _cmd_release(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        result = release_approved(conn, args.date, only_email=args.only_email)
        print(
            json.dumps(
                {
                    "date": result.brief_date,
                    "status": result.status,
                    "released": result.released,
                    "composed": result.composed,
                },
                ensure_ascii=False,
            )
        )
        return result.exit_code
    finally:
        conn.close()


def _cmd_stats(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        payload = stats.fetch_stats(conn, args.date)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))
        else:
            print(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True, indent=2))
        return 0
    finally:
        conn.close()


async def _cmd_crawl(_args: argparse.Namespace) -> int:
    conn = connect()
    try:
        total_new = 0

        def _sink(articles: list[storage.AiArticle]) -> None:
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


def _cmd_deliver(args: argparse.Namespace) -> int:
    conn = connect()
    try:
        res = deliverer.send_pending(
            conn,
            brief_date=args.date,
            retry_transient=args.retry_transient,
        )
        print(f"OK deliver attempted={res.attempted} sent={res.sent} failed={res.failed}")
        return 0
    finally:
        conn.close()


def main() -> int:
    args = _build_parser().parse_args()
    configure_logging(level=get_settings().log_level)
    if args.cmd == "daily":
        return asyncio.run(_cmd_daily(args))
    if args.cmd == "generate":
        return asyncio.run(_cmd_generate(args))
    if args.cmd == "preview-url":
        return _cmd_preview_url(args)
    if args.cmd == "approve":
        return _cmd_approve(args)
    if args.cmd == "release":
        return _cmd_release(args)
    if args.cmd == "crawl":
        return asyncio.run(_cmd_crawl(args))
    if args.cmd == "compose":
        return _cmd_compose(args)
    if args.cmd == "deliver":
        return _cmd_deliver(args)
    if args.cmd == "stats":
        return _cmd_stats(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
