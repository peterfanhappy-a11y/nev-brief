"""Top 4-6 vehicle sales card with user-aware brand ordering."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import psycopg


@dataclass(frozen=True)
class SalesEntry:
    brand_code: str
    brand_name: str
    units: int
    yoy: float | None
    wow: float | None


def fetch_latest_sales(
    conn: psycopg.Connection,
    on_or_before: date,
) -> list[SalesEntry]:
    """Latest week_date <= given date, one row per brand_code (most recent)."""
    sql = """
        SELECT DISTINCT ON (brand_code)
            brand_code, brand_name, units, yoy, wow
        FROM vehicle_sales_daily
        WHERE week_date <= %s
        ORDER BY brand_code, week_date DESC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (on_or_before,))
        return [SalesEntry(*r) for r in cur.fetchall()]


def rank_for_user(
    entries: list[SalesEntry],
    user_brands: list[str],
    top_k_min: int = 4,
    top_k_max: int = 6,
) -> list[SalesEntry]:
    """Reorder so user-followed brands come first; trim to [top_k_min, top_k_max].

    Followed brands keep their input order; un-followed sorted by units desc.
    If total entries < top_k_min, return all (no padding).
    """
    if not entries:
        return []
    user_set = set(user_brands)
    followed = [e for e in entries if e.brand_code in user_set]
    others = sorted(
        (e for e in entries if e.brand_code not in user_set),
        key=lambda e: -e.units,
    )
    combined = followed + others
    # Aim for top_k_max when data is plentiful; fall back to all when below top_k_min
    if len(combined) < top_k_min:
        return combined
    k = min(top_k_max, len(combined))
    return combined[:k]
