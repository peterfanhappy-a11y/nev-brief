"""AIVIZENS Resend payload tests — mock only the external SDK call."""
from __future__ import annotations

from typing import Any, cast
from unittest.mock import patch

import resend.exceptions as resend_exc
from ai_brief.resend_client import send_email
from tenacity import wait_none


def test_send_email_separates_body_confirmation_link_from_one_click_header() -> None:
    page_url = "https://aivizens.test/unsubscribe?token=tok-1&product=ai"
    api_url = "https://aivizens.test/api/unsubscribe?token=tok-1&product=ai"

    with (
        patch("ai_brief.resend_client._configure_sdk"),
        patch("ai_brief.resend_client.resend.Emails.send") as mock_send,
    ):
        mock_send.return_value = {"id": "re_abc123"}
        email_id = send_email(
            to="reader@example.com",
            subject="AIVIZENS",
            html=f'<a href="{page_url}">unsubscribe</a>',
            text=f"unsubscribe: {page_url}",
            idempotency_key="aivizens-2026-07-02-sub-1",
            one_click_unsubscribe_url=api_url,
        )

    assert email_id == "re_abc123"
    payload = mock_send.call_args.args[0]
    assert len(mock_send.call_args.args) == 2
    assert mock_send.call_args.args[1] == {
        "idempotency_key": "aivizens-2026-07-02-sub-1",
    }
    assert payload["html"] == f'<a href="{page_url}">unsubscribe</a>'
    assert payload["text"] == f"unsubscribe: {page_url}"
    assert payload["headers"]["List-Unsubscribe"] == f"<{api_url}>"
    assert payload["headers"]["List-Unsubscribe-Post"] == (
        "List-Unsubscribe=One-Click"
    )


def test_send_email_reuses_transport_idempotency_key_across_retries() -> None:
    idempotency_key = "aivizens-2026-07-02-sub-1"
    transient_error = resend_exc.ResendError(
        code=500,
        error_type="api_error",
        message="internal",
        suggested_action="retry",
    )

    with (
        patch("ai_brief.resend_client._configure_sdk"),
        patch("ai_brief.resend_client.resend.Emails.send") as mock_send,
    ):
        mock_send.side_effect = [transient_error, transient_error, {"id": "re_abc123"}]
        retry_without_wait = cast(Any, send_email).retry_with(wait=wait_none())
        email_id = retry_without_wait(
            to="reader@example.com",
            subject="AIVIZENS",
            html="<p>brief</p>",
            text="brief",
            idempotency_key=idempotency_key,
            one_click_unsubscribe_url="https://aivizens.test/api/unsubscribe?token=tok-1",
        )

    assert email_id == "re_abc123"
    assert mock_send.call_count == 3
    assert [call.args[1] for call in mock_send.call_args_list] == [
        {"idempotency_key": idempotency_key},
        {"idempotency_key": idempotency_key},
        {"idempotency_key": idempotency_key},
    ]
