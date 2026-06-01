"""Delivery storage — atomic claim + status updates.

claim_pending_deliveries uses UPDATE ... RETURNING + FOR UPDATE SKIP LOCKED so
multiple workers can run safely (same pattern as pipeline.storage.claim_pending).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import psycopg


@dataclass(frozen=True)
class PendingDelivery:
    delivery_id: str
    subscriber_id: str
    email: str
    brief_date: date
    content_html: str
    content_text: str
    unsubscribe_token: str


def claim_pending_deliveries(
    conn: psycopg.Connection,
    limit: int = 50,
) -> list[PendingDelivery]:
    """Atomically claim up to `limit` pending deliveries — mark them 'sending'
    and return their content. Other workers won't see these rows."""
    sql = """
        WITH claimed AS (
            SELECT d.id
            FROM deliveries d
            WHERE d.status = 'pending'
            ORDER BY d.created_at
            FOR UPDATE SKIP LOCKED
            LIMIT %s
        )
        UPDATE deliveries d
        SET status = 'sending', updated_at = NOW()
        FROM claimed
        WHERE d.id = claimed.id
        RETURNING
            d.id::text,
            d.subscriber_id::text,
            (SELECT email FROM subscribers WHERE id = d.subscriber_id),
            d.brief_date,
            d.content_html,
            d.content_text,
            (SELECT unsubscribe_token::text FROM subscribers WHERE id = d.subscriber_id);
    """
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
    return [
        PendingDelivery(
            delivery_id=r[0],
            subscriber_id=r[1],
            email=r[2],
            brief_date=r[3],
            content_html=r[4],
            content_text=r[5],
            unsubscribe_token=r[6],
        )
        for r in rows
    ]


def mark_sent(
    conn: psycopg.Connection,
    *,
    delivery_id: str,
    resend_email_id: str,
) -> None:
    sql = """
        UPDATE deliveries
        SET status = 'sent',
            resend_id = %s,
            sent_at = NOW(),
            error = NULL,
            updated_at = NOW()
        WHERE id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (resend_email_id, delivery_id))


def mark_failed(
    conn: psycopg.Connection,
    *,
    delivery_id: str,
    error: str,
) -> None:
    sql = """
        UPDATE deliveries
        SET status = 'failed',
            error = %s,
            retry_count = retry_count + 1,
            updated_at = NOW()
        WHERE id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (error[:500], delivery_id))


def reset_to_pending(
    conn: psycopg.Connection,
    *,
    delivery_id: str,
    error: str,
) -> None:
    """Transient failure — put back into pending queue for next run."""
    sql = """
        UPDATE deliveries
        SET status = 'pending',
            error = %s,
            retry_count = retry_count + 1,
            updated_at = NOW()
        WHERE id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (error[:500], delivery_id))
