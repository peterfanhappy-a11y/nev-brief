"""Resend SDK wrapper with retry + error classification.

Mirrors deepseek_client pattern: explicit fail-fast for auth/validation errors
so they don't burn 3 retries × exponential backoff.

SDK note: resend.exceptions.ResendError.__init__ signature is:
    (self, code, error_type, message, suggested_action, headers=None)
The `.code` attribute holds the HTTP status code; `.message` holds the detail.
"""
from __future__ import annotations

import resend
import resend.exceptions as resend_exc
from nev_shared.config import get_settings
from nev_shared.logger import get_logger
from nev_shared.net import no_proxy_env
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from nev_delivery.config import FROM_EMAIL, FROM_NAME

log = get_logger("delivery.resend")


class ResendError(Exception):
    """Base — any Resend failure surfaced by this wrapper."""


class ResendAuthError(ResendError):
    """Auth/permission errors (401/403). Fail-fast, no retry."""


class ResendPermanentError(ResendError):
    """4xx validation errors (422). Fail-fast, no retry."""


class ResendTransientError(ResendError):
    """5xx / 429 / network. Retried."""


def _configure_sdk() -> None:
    """Set resend.api_key from settings on each call (cheap, idempotent)."""
    resend.api_key = get_settings().resend_api_key


def _classify_and_raise(e: resend_exc.ResendError) -> None:
    """Translate Resend SDK exception → our typed exceptions."""
    code = getattr(e, "code", 0) or 0
    msg = getattr(e, "message", str(e))
    if code in (401, 403):
        raise ResendAuthError(f"{code} {msg}") from e
    if 400 <= code < 500 and code != 429:
        raise ResendPermanentError(f"{code} {msg}") from e
    raise ResendTransientError(f"{code} {msg}") from e


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(ResendTransientError),
    reraise=True,
)
def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
    idempotency_key: str,
    unsubscribe_url: str,
) -> str:
    """Send one email via Resend. Returns Resend email ID.

    Raises ResendAuthError / ResendPermanentError / ResendTransientError.
    """
    _configure_sdk()
    params: dict = {
        "from": f"{FROM_NAME} <{FROM_EMAIL}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
        "headers": {
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            "Idempotency-Key": idempotency_key,
        },
    }
    # resend SDK uses requests internally with no trust_env hook, so strip
    # proxy env vars for the duration of this call (process-local pop, restored
    # on exit) — keeps Clash / SOCKS proxy out of the loop without affecting
    # other programs on the host.
    try:
        with no_proxy_env():
            result = resend.Emails.send(params)
    except resend_exc.ResendError as e:
        _classify_and_raise(e)
        raise  # unreachable — satisfy type checker
    email_id = result.get("id") if isinstance(result, dict) else None
    if not email_id:
        raise ResendPermanentError(f"Resend returned no id: {result!r}")
    log.info("resend.sent", to=to, email_id=email_id)
    return email_id
