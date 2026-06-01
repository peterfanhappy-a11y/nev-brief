"""Storage SQL-shape tests — mock psycopg.Connection."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from nev_delivery.storage import (
    PendingDelivery,
    claim_pending_deliveries,
    mark_failed,
    mark_sent,
)


def _mock_conn_with_rows(rows: list[tuple]) -> MagicMock:
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = rows
    return conn


def test_claim_pending_returns_pendingdeliveries():
    rows = [
        ("did-1", "sid-1", "peter@x.com", "2026-05-29", "<html>", "text",
         "<unsub-token>"),
    ]
    conn = _mock_conn_with_rows(rows)
    result = claim_pending_deliveries(conn, limit=10)
    assert len(result) == 1
    assert result[0].delivery_id == "did-1"
    assert result[0].subscriber_id == "sid-1"
    assert result[0].email == "peter@x.com"
    sql_called = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
    assert "FOR UPDATE SKIP LOCKED" in sql_called
    assert "RETURNING" in sql_called
    assert "'sending'" in sql_called


def test_mark_sent_updates_status_and_resend_id():
    conn = _mock_conn_with_rows([])
    mark_sent(conn, delivery_id="did-1", resend_email_id="re_abc")
    sql_called = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
    params = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][1]
    assert "UPDATE deliveries" in sql_called
    assert "'sent'" in sql_called
    assert "sent_at = NOW()" in sql_called
    assert "re_abc" in params


def test_mark_failed_sets_status_and_error():
    conn = _mock_conn_with_rows([])
    mark_failed(conn, delivery_id="did-1", error="401 invalid_api_key")
    sql_called = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
    params = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][1]
    assert "UPDATE deliveries" in sql_called
    assert "'failed'" in sql_called
    assert "retry_count = retry_count + 1" in sql_called
    assert "401 invalid_api_key" in params
