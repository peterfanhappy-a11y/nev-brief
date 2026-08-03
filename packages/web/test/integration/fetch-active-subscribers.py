"""Exercise the production active-subscriber selector against the test database."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

import psycopg
from ai_brief.storage import fetch_active_subscribers


def main() -> int:
    with psycopg.connect(sys.argv[1]) as connection:
        rows = fetch_active_subscribers(connection)
    print(json.dumps([asdict(row) for row in rows], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
