"""vehicle_sales_daily I/O."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Iterable

import psycopg

if TYPE_CHECKING:
    from nev_summarizer.sales.caam_parser import SalesRecord


def upsert_vehicle_sales_records(
    conn: psycopg.Connection,
    records: Iterable[SalesRecord],
    week_date: date,
    source: str,
) -> int:
    """UPSERT each record by (brand_code, week_date, source).

    Returns number of rows successfully upserted.
    """
    sql = """
        INSERT INTO vehicle_sales_daily
            (brand_code, brand_name, week_date, units, yoy, wow, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (brand_code, week_date, source) DO UPDATE SET
            brand_name = EXCLUDED.brand_name,
            units      = EXCLUDED.units,
            yoy        = EXCLUDED.yoy,
            wow        = EXCLUDED.wow,
            updated_at = NOW();
    """
    count = 0
    with conn.cursor() as cur:
        for r in records:
            cur.execute(
                sql,
                (r.brand_code, r.brand_name, week_date, r.units, r.yoy, r.wow, source),
            )
            count += 1
    return count
