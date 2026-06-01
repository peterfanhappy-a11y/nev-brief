# packages/delivery/tests/integration/test_sender_e2e.py
"""E2E: real Supabase pooler DB + mocked Resend.

Inserts a fixture subscriber + delivery, runs send_pending with Resend mocked,
verifies status transitions to 'sent' with resend_id populated.

claim_pending_deliveries is also patched so the real peter.fan.happy@gmail.com
pending row is not touched during the test.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch
from uuid import uuid4

import psycopg
import pytest
from nev_delivery.sender import send_pending
from nev_delivery.storage import PendingDelivery
from nev_shared.config import get_settings


@pytest.fixture
def db_conn():
    settings = get_settings()
    conn = psycopg.connect(settings.database_url)
    yield conn
    conn.rollback()
    conn.close()


def test_sender_e2e_marks_sent(db_conn):
    """Insert one pending delivery, send_pending → status='sent', resend_id set."""
    sub_id = str(uuid4())
    email = f"e2e-{sub_id[:8]}@test.local"
    brief_d = date(2026, 5, 28)

    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO subscribers (id, email, push_time, status, unsubscribe_token) "
            "VALUES (%s, %s, '08:00', 'active', gen_random_uuid());",
            (sub_id, email),
        )
        cur.execute(
            "INSERT INTO deliveries (subscriber_id, brief_date, content_html, "
            "content_text, status) VALUES (%s, %s, '<p>hi</p>', 'hi', 'pending') "
            "RETURNING id::text;",
            (sub_id, brief_d),
        )
        delivery_id = cur.fetchone()[0]
    db_conn.commit()

    try:
        # Patch claim_pending_deliveries to return ONLY our test row so the real
        # peter.fan.happy@gmail.com pending delivery is not mutated during the test.
        test_pending = PendingDelivery(
            delivery_id=delivery_id,
            subscriber_id=sub_id,
            email=email,
            brief_date=brief_d,
            content_html="<p>hi</p>",
            content_text="hi",
            unsubscribe_token="00000000-0000-0000-0000-000000000000",
        )
        with patch("nev_delivery.sender.claim_pending_deliveries", return_value=[test_pending]), \
             patch("nev_delivery.sender.send_email", return_value="re_e2e_123"):
            result = send_pending(db_conn, limit=10)
        assert result.sent >= 1

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT status, resend_id, sent_at FROM deliveries WHERE id = %s;",
                (delivery_id,),
            )
            row = cur.fetchone()
        assert row[0] == "sent"
        assert row[1] == "re_e2e_123"
        assert row[2] is not None
    finally:
        # Cleanup — even if assertions fail
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM deliveries WHERE id = %s;", (delivery_id,))
            cur.execute("DELETE FROM subscribers WHERE id = %s;", (sub_id,))
        db_conn.commit()
