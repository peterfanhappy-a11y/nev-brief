from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from ai_brief import deliverer, storage
from ai_brief.storage import PendingAiDelivery


def _pending() -> PendingAiDelivery:
    return PendingAiDelivery(
        delivery_id="d-1",
        subscriber_id="sub-1",
        email="reader@example.com",
        brief_date=date(2026, 8, 13),
        subject="AIVIZENS",
        content_html='<a href="https://aivizens.test/unsubscribe?token=t">退订</a>',
        content_text="退订：https://aivizens.test/unsubscribe?token=t",
        unsubscribe_token="t",  # noqa: S105, S106 - inert test value
    )


def test_send_disabled_does_not_claim_or_send(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_EMAIL_SEND_ENABLED", "false")
    conn = MagicMock()
    with patch.object(storage, "claim_pending_deliveries") as claim:
        result = deliverer.send_pending(conn)
    assert result.attempted == result.sent == result.failed == 0
    claim.assert_not_called()


def test_idempotency_key_is_stable_even_if_legacy_suffix_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_IDEMPOTENCY_SUFFIX", "unsafe-test-override")
    conn = MagicMock()
    with (
        patch.object(storage, "lock_active_subscriber", return_value=True),
        patch.object(deliverer, "send_email", return_value="re_1") as send,
        patch.object(storage, "mark_sent"),
    ):
        assert deliverer._send_one(conn, _pending()) is True
    assert send.call_args.kwargs["idempotency_key"] == "aivizens-2026-08-13-sub-1"


def test_retry_only_targets_transient_failures_below_ceiling() -> None:
    from unittest.mock import patch

    conn = MagicMock()
    with patch("ai_brief.config.email_send_enabled", return_value=True), patch.object(
        storage, "retry_transient_deliveries", return_value=2
    ) as retry:
        deliverer.send_pending(conn, brief_date=date(2026, 8, 13), retry_transient=True)
    retry.assert_called_once_with(conn, brief_date=date(2026, 8, 13))
