"""nev_composer CLI — python -m nev_composer run [--date YYYY-MM-DD] [--subscriber EMAIL]"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone

import psycopg

from nev_shared.config import get_settings
from nev_shared.logger import configure_logging, get_logger

from nev_composer.runner import run_for_date

log = get_logger("composer.cli")


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m nev_composer")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="为当日 active 订阅者生成 deliveries")
    run.add_argument("--date", type=_parse_date, default=None,
                     help="brief_date YYYY-MM-DD (默认今天 UTC)")
    run.add_argument("--subscriber", default=None,
                     help="只为指定 email 生成（测试用）")
    run.add_argument("--top-n", type=int, default=10, help="Top N 截取（默认 10）")
    return p


def main() -> int:
    settings = get_settings()
    configure_logging(level=settings.log_level)

    args = _build_parser().parse_args()
    if args.cmd != "run":
        return 2

    brief_date = args.date or datetime.now(timezone.utc).date()
    conn = psycopg.connect(settings.database_url)
    try:
        result = run_for_date(
            conn, brief_date,
            top_n=args.top_n,
            only_subscriber_email=args.subscriber,
        )
        print(
            f"OK brief={result['brief_date']} subscribers={result['subscribers']} "
            f"composed={result['composed']} failed={result.get('failed', 0)}"
        )
        return 0
    finally:
        # Note: commits are done per-subscriber inside run_for_date; no final commit needed
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
