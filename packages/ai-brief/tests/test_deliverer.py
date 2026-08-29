"""deliverer 单测 — mock send_email + storage，验证 sent/failed/transient 分支 + 幂等键。"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from ai_brief import config, deliverer, storage
from ai_brief.resend_client import ResendAuthError, ResendTransientError
from ai_brief.storage import PendingAiDelivery


def _pending() -> PendingAiDelivery:
    return PendingAiDelivery(
        delivery_id="d-1", subscriber_id="sub-1", email="a@x.com",
        brief_date=date(2026, 7, 2), subject="今日主题",
        content_html=(
            '<a href="https://aivizens.test/unsubscribe?token=tok-1&product=ai">'
            "unsubscribe</a>"
        ),
        content_text=(
            "unsubscribe: "
            "https://aivizens.test/unsubscribe?token=tok-1&product=ai"
        ),
        unsubscribe_token="tok-1",  # noqa: S106 - inert test value
    )


def test_send_one_success() -> None:
    conn = MagicMock()
    with patch.object(storage, "lock_active_subscriber", return_value=True), \
         patch.object(deliverer, "send_email", return_value="re_123") as mock_send, \
         patch("ai_brief.config.WEB_BASE_URL", "https://aivizens.test"), \
         patch.object(storage, "mark_sent") as mark_sent, \
         patch.object(deliverer, "log") as mock_log:
        ok = deliverer._send_one(conn, _pending())
    assert ok is True
    mark_sent.assert_called_once()
    # 幂等键 aivizens-{date}-{sub}
    kwargs = mock_send.call_args.kwargs
    assert kwargs["idempotency_key"] == "aivizens-2026-07-02-sub-1"
    assert kwargs["subject"] == "今日主题"
    assert kwargs["one_click_unsubscribe_url"] == (
        "https://aivizens.test/api/unsubscribe?token=tok-1&product=ai"
    )
    assert "https://aivizens.test/unsubscribe?token=tok-1&product=ai" in kwargs["html"]
    assert "https://aivizens.test/unsubscribe?token=tok-1&product=ai" in kwargs["text"]
    assert "/api/unsubscribe" not in kwargs["html"]
    assert "/api/unsubscribe" not in kwargs["text"]
    conn.commit.assert_called()
    assert "a@x.com" not in repr(mock_log.mock_calls)


def test_send_one_auth_error_marks_failed() -> None:
    conn = MagicMock()
    with patch.object(storage, "lock_active_subscriber", return_value=True), \
         patch.object(
             deliverer,
             "send_email",
             side_effect=ResendAuthError("private provider payload a@x.com"),
         ), \
         patch.object(storage, "mark_failed") as mark_failed, \
         patch.object(deliverer, "log") as mock_log:
        ok = deliverer._send_one(conn, _pending())
    assert ok is False
    mark_failed.assert_called_once()
    assert "a@x.com" not in repr(mock_log.mock_calls)
    assert "private provider payload" not in repr(mock_log.mock_calls)


def test_send_one_transient_is_recorded_for_explicit_retry() -> None:
    conn = MagicMock()
    with patch.object(storage, "lock_active_subscriber", return_value=True), \
         patch.object(
             deliverer,
             "send_email",
             side_effect=ResendTransientError("private provider payload a@x.com"),
         ), \
         patch.object(storage, "mark_failed") as mark_failed, \
         patch.object(deliverer, "log") as mock_log:
        ok = deliverer._send_one(conn, _pending())
    assert ok is False
    mark_failed.assert_called_once_with(
        conn, delivery_id="d-1", error="transient:ResendTransientError"
    )
    assert "a@x.com" not in repr(mock_log.mock_calls)
    assert "private provider payload" not in repr(mock_log.mock_calls)


def test_send_one_suppresses_delivery_after_unsubscribe() -> None:
    conn = MagicMock()
    with patch.object(storage, "lock_active_subscriber", return_value=False), \
         patch.object(deliverer, "send_email") as mock_send, \
         patch.object(storage, "mark_suppressed") as mark_suppressed:
        ok = deliverer._send_one(conn, _pending())
    assert ok is False
    mock_send.assert_not_called()
    mark_suppressed.assert_called_once_with(conn, delivery_id="d-1")
    conn.commit.assert_called_once()


def test_send_pending_empty() -> None:
    conn = MagicMock()
    with patch.object(storage, "claim_pending_deliveries", return_value=[]):
        res = deliverer.send_pending(conn)
    assert res.attempted == 0 and res.sent == 0


def test_send_pending_mixed() -> None:
    conn = MagicMock()
    pendings = [_pending(), _pending()]
    with patch.object(config, "email_send_enabled", return_value=True), \
         patch.object(storage, "claim_pending_deliveries", return_value=pendings), \
         patch.object(deliverer, "_send_one", side_effect=[True, False]):
        res = deliverer.send_pending(conn)
    assert res.attempted == 2 and res.sent == 1 and res.failed == 1
