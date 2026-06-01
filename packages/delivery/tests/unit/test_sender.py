"""Sender main-loop unit tests — fake storage + fake resend_client."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from nev_delivery.resend_client import ResendAuthError, ResendTransientError
from nev_delivery.sender import SendResult, send_pending
from nev_delivery.storage import PendingDelivery

PENDING = PendingDelivery(
    delivery_id="did-1",
    subscriber_id="sid-1",
    email="peter@x.com",
    brief_date=date(2026, 5, 29),
    content_html="<p>hi</p>",
    content_text="hi",
    unsubscribe_token="unsub-abc",
)


def _conn() -> MagicMock:
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = MagicMock()
    return conn


def test_send_pending_marks_sent_on_success():
    conn = _conn()
    with patch("nev_delivery.sender.claim_pending_deliveries", return_value=[PENDING]), \
         patch("nev_delivery.sender.send_email", return_value="re_abc"), \
         patch("nev_delivery.sender.mark_sent") as mark_sent, \
         patch("nev_delivery.sender.mark_failed"):
        result = send_pending(conn, limit=10)
    assert result.attempted == 1
    assert result.sent == 1
    assert result.failed == 0
    mark_sent.assert_called_once()
    assert conn.commit.call_count >= 1


def test_send_pending_marks_failed_on_auth_error():
    conn = _conn()
    with patch("nev_delivery.sender.claim_pending_deliveries", return_value=[PENDING]), \
         patch("nev_delivery.sender.send_email", side_effect=ResendAuthError("401")), \
         patch("nev_delivery.sender.mark_sent"), \
         patch("nev_delivery.sender.mark_failed") as mark_failed:
        result = send_pending(conn, limit=10)
    assert result.failed == 1
    assert result.sent == 0
    mark_failed.assert_called_once()


def test_send_pending_resets_to_pending_on_transient():
    conn = _conn()
    with patch("nev_delivery.sender.claim_pending_deliveries", return_value=[PENDING]), \
         patch("nev_delivery.sender.send_email", side_effect=ResendTransientError("500")), \
         patch("nev_delivery.sender.reset_to_pending") as reset:
        result = send_pending(conn, limit=10)
    assert result.failed == 1
    reset.assert_called_once()


def test_send_pending_subject_includes_chinese_date():
    """Subject should be '【NEV 早报】2026-05-29 · 10 条新闻'."""
    conn = _conn()
    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return "re_x"

    with patch("nev_delivery.sender.claim_pending_deliveries", return_value=[PENDING]), \
         patch("nev_delivery.sender.send_email", side_effect=fake_send), \
         patch("nev_delivery.sender.mark_sent"):
        send_pending(conn, limit=10)
    assert "2026-05-29" in captured["subject"]
    assert captured["idempotency_key"] == "nev-2026-05-29-sid-1"


def test_send_pending_no_rows_returns_zero():
    conn = _conn()
    with patch("nev_delivery.sender.claim_pending_deliveries", return_value=[]):
        result = send_pending(conn, limit=10)
    assert result.attempted == 0
