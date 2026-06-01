"""nev-delivery CLI — `python -m nev_delivery send [--limit N] [--dry-run]`."""
from __future__ import annotations

import argparse
import sys

import psycopg
from nev_shared.config import get_settings
from nev_shared.logger import get_logger

from nev_delivery.sender import send_pending

log = get_logger("delivery.cli")


def _cmd_send(args: argparse.Namespace) -> int:
    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        if args.dry_run:
            # Don't claim — just preview what would be sent.
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT d.id, s.email, d.brief_date "
                    "FROM deliveries d JOIN subscribers s ON s.id = d.subscriber_id "
                    "WHERE d.status = 'pending' "
                    "ORDER BY d.created_at LIMIT %s;",
                    (args.limit,),
                )
                rows = cur.fetchall()
            print(f"DRY-RUN: would send {len(rows)} delivery(ies):")
            for r in rows:
                print(f"  - {r[0]} -> {r[1]} (brief_date={r[2]})")
            return 0

        result = send_pending(conn, limit=args.limit)
        conn.commit()
    print(f"OK attempted={result.attempted} sent={result.sent} failed={result.failed}")
    return 0 if result.failed == 0 else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nev-delivery")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_send = sub.add_parser("send", help="Drain pending deliveries via Resend")
    p_send.add_argument("--limit", type=int, default=50)
    p_send.add_argument("--dry-run", action="store_true",
                        help="Preview pending rows without sending")
    p_send.set_defaults(func=_cmd_send)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
