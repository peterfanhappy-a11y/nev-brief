"""Privacy-safe operational statistics for the AIVIZENS CLI."""
from __future__ import annotations

from datetime import date
from typing import Any

import psycopg


def fetch_stats(conn: psycopg.Connection, brief_date: date | None = None) -> dict[str, Any]:
    """Return only aggregate operational data; never select recipient-level rows."""
    result: dict[str, Any] = {"date": brief_date.isoformat() if brief_date else None}
    queries: dict[str, tuple[str, tuple[Any, ...]]]
    if brief_date is None:
        queries = {
            "subscriptions": ("SELECT * FROM ai_subscription_stats", ()),
            "deliveries": ("SELECT * FROM ai_delivery_stats", ()),
            "ratings": ("SELECT * FROM ai_rating_stats", ()),
            "operations": ("SELECT * FROM ai_daily_operations", ()),
        }
    else:
        queries = {
            "subscriptions": ("SELECT * FROM ai_subscription_stats", ()),
            "deliveries": ("SELECT * FROM ai_delivery_stats WHERE brief_date = %s", (brief_date,)),
            "ratings": ("SELECT * FROM ai_rating_stats WHERE brief_date = %s", (brief_date,)),
            "operations": (
                "SELECT * FROM ai_daily_operations WHERE brief_date = %s",
                (brief_date,),
            ),
        }
    for key, (sql, params) in queries.items():
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [column.name for column in (cur.description or [])]
            rows = cur.fetchall()
        result[key] = [dict(zip(columns, row, strict=True)) for row in rows]
    return result
