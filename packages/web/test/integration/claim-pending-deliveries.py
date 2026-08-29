"""Exercise the production delivery claim against the test database."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

import psycopg
from ai_brief.storage import claim_pending_deliveries


def main() -> int:
    with psycopg.connect(sys.argv[1]) as connection:
        rows = claim_pending_deliveries(connection)
    print(json.dumps([asdict(row) for row in rows], default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
