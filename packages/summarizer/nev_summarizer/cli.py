"""nev_summarizer CLI — python -m nev_summarizer run|sales-extract"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime, timezone

import psycopg

from nev_shared.config import get_settings
from nev_shared.logger import configure_logging, get_logger

from nev_summarizer.runner import run_brief_for_date, DEFAULT_TOP_N

log = get_logger("summarizer.cli")


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_month(value: str) -> str:
    """Accept YYYY-MM and validate parse-ability."""
    datetime.strptime(value, "%Y-%m")
    return value


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m nev_summarizer")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="生成当日早报候选")
    run.add_argument("--date", type=_parse_date, default=None,
                     help="brief_date YYYY-MM-DD (默认今天 UTC)")
    run.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                     help=f"候选数上限 (默认 {DEFAULT_TOP_N})")

    sales = sub.add_parser("sales-extract", help="从 CAAM 月报抽销量")
    sales.add_argument("--month", type=_parse_month, required=True,
                       help="目标月份 YYYY-MM")
    sales.add_argument("--limit", type=int, default=10,
                       help="单次最多处理几篇 CAAM 月报")
    return p


async def _async_run(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    conn = psycopg.connect(settings.database_url)
    try:
        brief_date = args.date or datetime.now(timezone.utc).date()
        result = await run_brief_for_date(conn, brief_date, top_n=args.top_n)
        print(
            f"OK brief={result['brief_date']} clusters={result['clusters']} "
            f"summarized={result['summarized']} truncated={result['truncated']}"
        )
        return 0 if result["summarized"] > 0 else 0   # 空也算成功 — 表示今天没数据
    finally:
        conn.close()


async def _async_sales(args: argparse.Namespace) -> int:
    from nev_summarizer.sales.caam_parser import run_caam_extraction
    settings = get_settings()
    configure_logging(level=settings.log_level)
    conn = psycopg.connect(settings.database_url)
    try:
        result = await run_caam_extraction(conn, args.month, limit=args.limit)
        print(
            f"OK month={args.month} articles={result['articles_processed']} "
            f"sales_rows={result['sales_upserted']}"
        )
        return 0
    finally:
        conn.close()


def main() -> int:
    args = _build_parser().parse_args()
    if args.cmd == "run":
        return asyncio.run(_async_run(args))
    if args.cmd == "sales-extract":
        return asyncio.run(_async_sales(args))
    return 2


if __name__ == "__main__":
    sys.exit(main())
