#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --date YYYY-MM-DD [--production-read-only]" >&2
  exit 2
}

DATE=""
PRODUCTION_READ_ONLY=0
while (($#)); do
  case "$1" in
    --date) DATE="${2:-}"; shift 2 ;;
    --production-read-only) PRODUCTION_READ_ONLY=1; shift ;;
    *) usage ;;
  esac
done
[[ "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || usage

: "${DATABASE_URL:?DATABASE_URL is required}"
if [[ "$DATABASE_URL" == *supabase.co* || "$DATABASE_URL" == *supabase.com* ]]; then
  (( PRODUCTION_READ_ONLY == 1 )) || {
    echo "refusing production database; pass --production-read-only for read-only checks" >&2
    exit 3
  }
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
exec uv run python - "$DATE" <<'PY'
from __future__ import annotations

import os
import sys
from datetime import date

import psycopg

brief_date = date.fromisoformat(sys.argv[1])
with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, count(*)
            FROM ai_daily_briefs
            WHERE brief_date = %s
            GROUP BY status
            ORDER BY status
            """,
            (brief_date,),
        )
        statuses = [(str(status), int(count)) for status, count in cur.fetchall()]
        cur.execute(
            """
            SELECT status, count(*)
            FROM ai_deliveries
            WHERE brief_date = %s
            GROUP BY status
            ORDER BY status
            """,
            (brief_date,),
        )
        deliveries = [(str(status), int(count)) for status, count in cur.fetchall()]

print(f"workflow date={brief_date.isoformat()}")
print("brief_status_counts=" + ",".join(f"{s}:{n}" for s, n in statuses) or "brief_status_counts=")
print("delivery_status_counts=" + ",".join(f"{s}:{n}" for s, n in deliveries) or "delivery_status_counts=")
PY
