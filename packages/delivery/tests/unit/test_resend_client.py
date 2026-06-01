"""Resend client wrapper unit tests — mock resend.Emails.send."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from nev_delivery.resend_client import (
    ResendAuthError,
    ResendPermanentError,
    ResendTransientError,
    send_email,
)


def test_send_email_success():
    """Happy path: resend returns {id, ...} → wrapper returns id."""
    with patch("nev_delivery.resend_client.resend.Emails.send") as mock_send:
        mock_send.return_value = {"id": "re_abc123"}
        email_id = send_email(
            to="peter@example.com",
            subject="Test",
            html="<p>hi</p>",
            text="hi",
            idempotency_key="nev-2026-06-01-uid",
            unsubscribe_url="https://nev.example/unsub?t=abc",
        )
    assert email_id == "re_abc123"
    call_kwargs = mock_send.call_args[0][0]
    assert call_kwargs["to"] == ["peter@example.com"]
    assert call_kwargs["from"].startswith("NEV 早报 <")
    assert "List-Unsubscribe" in call_kwargs.get("headers", {})


def test_send_email_auth_error_fails_fast():
    """401 → ResendAuthError, no retry."""
    import resend.exceptions as rex

    with patch("nev_delivery.resend_client.resend.Emails.send") as mock_send:
        mock_send.side_effect = rex.ResendError(
            code=401,
            error_type="authentication_error",
            message="invalid_api_key",
            suggested_action="check key",
        )
        with pytest.raises(ResendAuthError):
            send_email(
                to="x@y.com", subject="S", html="h", text="t",
                idempotency_key="k", unsubscribe_url="u",
            )
    assert mock_send.call_count == 1  # no retry


def test_send_email_invalid_email_fails_fast():
    """422 validation error → ResendPermanentError, no retry."""
    import resend.exceptions as rex

    with patch("nev_delivery.resend_client.resend.Emails.send") as mock_send:
        mock_send.side_effect = rex.ResendError(
            code=422,
            error_type="validation_error",
            message="invalid_to_email",
            suggested_action="fix email",
        )
        with pytest.raises(ResendPermanentError):
            send_email(
                to="bad", subject="S", html="h", text="t",
                idempotency_key="k", unsubscribe_url="u",
            )
    assert mock_send.call_count == 1


def test_send_email_5xx_retries_then_raises():
    """500 → ResendTransientError, retried 3 times then raised."""
    import resend.exceptions as rex

    with patch("nev_delivery.resend_client.resend.Emails.send") as mock_send:
        mock_send.side_effect = rex.ResendError(
            code=500,
            error_type="api_error",
            message="internal",
            suggested_action="retry",
        )
        with pytest.raises(ResendTransientError):
            send_email(
                to="x@y.com", subject="S", html="h", text="t",
                idempotency_key="k", unsubscribe_url="u",
            )
    assert mock_send.call_count == 3
