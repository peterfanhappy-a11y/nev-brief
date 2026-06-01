"""Composer DB I/O — read daily_briefs/subscribers/prefs, write deliveries."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg


@dataclass(frozen=True)
class ActiveSubscriber:
    id: str
    email: str
    push_time: str
    unsubscribe_token: str
    pref_brands: list[str]
    pref_topics: list[str]


def fetch_daily_brief_candidates(
    conn: psycopg.Connection,
    brief_date: date,
) -> list[dict[str, Any]] | None:
    """Return candidates list for brief_date, or None if no brief generated yet."""
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
    return raw


def fetch_active_subscribers(conn: psycopg.Connection) -> list[ActiveSubscriber]:
    """JOIN subscribers + subscriber_preferences, only status='active'."""
    sql = """
        SELECT s.id::text, s.email, s.push_time::text, s.unsubscribe_token::text,
               COALESCE(p.brands, '{}') AS brands,
               COALESCE(p.topics, '{}') AS topics
        FROM subscribers s
        LEFT JOIN subscriber_preferences p ON p.subscriber_id = s.id
        WHERE s.status = 'active';
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [
        ActiveSubscriber(
            id=r[0], email=r[1], push_time=r[2], unsubscribe_token=r[3],
            pref_brands=list(r[4] or []),
            pref_topics=list(r[5] or []),
        )
        for r in rows
    ]


def upsert_delivery(
    conn: psycopg.Connection,
    subscriber_id: str,
    brief_date: date,
    content_html: str,
    content_text: str,
    selected_items: list[str],
) -> None:
    """UPSERT by (subscriber_id, brief_date) — idempotent re-runs."""
    sql = """
        INSERT INTO deliveries
            (subscriber_id, brief_date, content_html, content_text, selected_items, status)
        VALUES (%s, %s, %s, %s, %s::jsonb, 'pending')
        ON CONFLICT (subscriber_id, brief_date) DO UPDATE SET
            content_html   = EXCLUDED.content_html,
            content_text   = EXCLUDED.content_text,
            selected_items = EXCLUDED.selected_items,
            status         = 'pending',
            updated_at     = NOW();
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            subscriber_id, brief_date, content_html, content_text,
            json.dumps(selected_items),
        ))
