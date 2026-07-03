"""deliverer 单测 — mock send_email + storage，验证 sent/failed/transient 分支 + 幂等键。"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from ai_brief import deliverer
from ai_brief.resend_client import ResendAuthError, ResendTransientError
from ai_brief.storage import PendingAiDelivery


def _pending() -> PendingAiDelivery:
    return PendingAiDelivery(
        delivery_id="d-1", subscriber_id="sub-1", email="a@x.com",
        brief_date=date(2026, 7, 2), subject="今日主题",
        content_html="<html>", content_text="text", unsubscribe_token="tok-1",
    )


def test_send_one_success() -> None:
    conn = MagicMock()
    with patch.object(deliverer, "send_email", return_value="re_123") as mock_send, \
         patch.object(deliverer.storage, "mark_sent") as mark_sent:
        ok = deliverer._send_one(conn, _pending())
    assert ok is True
    mark_sent.assert_called_once()
    # 幂等键 ai-{date}-{sub}
    kwargs = mock_send.call_args.kwargs
    assert kwargs["idempotency_key"] == "ai-2026-07-02-sub-1"
    assert kwargs["subject"] == "今日主题"
    assert "product=ai" in kwargs["unsubscribe_url"]
    conn.commit.assert_called()


def test_send_one_auth_error_marks_failed() -> None:
    conn = MagicMock()
    with patch.object(deliverer, "send_email", side_effect=ResendAuthError("401")), \
         patch.object(deliverer.storage, "mark_failed") as mark_failed:
        ok = deliverer._send_one(conn, _pending())
    assert ok is False
    mark_failed.assert_called_once()


def test_send_one_transient_resets() -> None:
    conn = MagicMock()
    with patch.object(deliverer, "send_email", side_effect=ResendTransientError("503")), \
         patch.object(deliverer.storage, "reset_to_pending") as reset:
        ok = deliverer._send_one(conn, _pending())
    assert ok is False
    reset.assert_called_once()


def test_send_pending_empty() -> None:
    conn = MagicMock()
    with patch.object(deliverer.storage, "claim_pending_deliveries", return_value=[]):
        res = deliverer.send_pending(conn)
    assert res.attempted == 0 and res.sent == 0


def test_send_pending_mixed() -> None:
    conn = MagicMock()
    pendings = [_pending(), _pending()]
    with patch.object(deliverer.storage, "claim_pending_deliveries", return_value=pendings), \
         patch.object(deliverer, "_send_one", side_effect=[True, False]):
        res = deliverer.send_pending(conn)
    assert res.attempted == 2 and res.sent == 1 and res.failed == 1
