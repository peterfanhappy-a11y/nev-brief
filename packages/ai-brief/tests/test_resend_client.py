"""AIVIZENS Resend payload tests — mock only the external SDK call."""
from __future__ import annotations

from unittest.mock import patch

from ai_brief.resend_client import send_email


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
    assert payload["html"] == f'<a href="{page_url}">unsubscribe</a>'
    assert payload["text"] == f"unsubscribe: {page_url}"
    assert payload["headers"]["List-Unsubscribe"] == f"<{api_url}>"
    assert payload["headers"]["List-Unsubscribe-Post"] == (
        "List-Unsubscribe=One-Click"
    )
