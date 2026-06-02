"""nev-orchestrator CLI — daily pipeline 触发与重放。

Examples:
    python -m nev_orchestrator daily
    python -m nev_orchestrator daily --date 2026-06-01
    python -m nev_orchestrator daily --resume compose
    python -m nev_orchestrator daily --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone

from nev_shared.logger import get_logger

from nev_orchestrator.runner import run_daily

log = get_logger("orchestrator.cli")


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _cmd_daily(args: argparse.Namespace) -> int:
    target = args.date or datetime.now(timezone.utc).date()
    result = run_daily(brief_date=target, dry_run=args.dry_run, resume=args.resume)
    print(
        f"daily {target.isoformat()} "
        f"succeeded={len(result.succeeded_steps)} "
        f"failed={len(result.failed_steps)} "
        f"aborted={result.aborted} "
        f"duration={result.duration_seconds:.0f}s"
    )
    return 0 if result.success else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nev-orchestrator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_daily = sub.add_parser("daily", help="执行一日完整 pipeline")
    p_daily.add_argument("--date", type=_parse_date, default=None,
                         help="brief_date YYYY-MM-DD (默认今日 UTC)")
    p_daily.add_argument("--dry-run", action="store_true",
                         help="只打印步骤，不执行子进程")
    p_daily.add_argument("--resume", type=str, default=None,
                         choices=["sync", "crawl", "pipeline", "summarize",
                                  "sales", "compose", "deliver"],
                         help="从指定 step 开始")
    p_daily.set_defaults(func=_cmd_daily)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
