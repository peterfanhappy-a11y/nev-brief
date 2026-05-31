"""Daily brief I/O — UPSERT semantics by brief_date."""
from __future__ import annotations

import json
from datetime import date
from typing import Any

import psycopg


def upsert_daily_brief(
    conn: psycopg.Connection,
    brief_date: date,
    candidates: list[dict[str, Any]],
) -> None:
    """INSERT ... ON CONFLICT (brief_date) DO UPDATE — idempotent re-runs.

    candidates is serialized to jsonb. Order is preserved.
    """
    sql = """
        INSERT INTO daily_briefs (brief_date, candidates, generated_at)
        VALUES (%s, %s::jsonb, NOW())
        ON CONFLICT (brief_date) DO UPDATE SET
            candidates = EXCLUDED.candidates,
            generated_at = NOW(),
            updated_at = NOW();
    """
    with conn.cursor() as cur:
        cur.execute(sql, (brief_date, json.dumps(candidates, ensure_ascii=False)))


def fetch_daily_brief(
    conn: psycopg.Connection,
    brief_date: date,
) -> list[dict[str, Any]] | None:
    """Return the candidates jsonb for brief_date, or None if not yet generated."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT candidates FROM daily_briefs WHERE brief_date = %s;",
            (brief_date,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    raw = row[0]
    if isinstance(raw, (str, bytes)):
        return json.loads(raw)
    return raw  # psycopg may auto-parse jsonb to Python list/dict
