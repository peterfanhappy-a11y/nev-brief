"""Generate short-lived signed URLs for the read-only daily brief preview."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import date

MAX_PREVIEW_LIFETIME_SECONDS = 900
MIN_NON_TEST_SECRET_BYTES = 32
_MAX_UNIX_SECONDS = 9_999_999_999


def _validate_date(value: str) -> None:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("brief date must use canonical YYYY-MM-DD format") from exc
    if parsed.isoformat() != value:
        raise ValueError("brief date must use canonical YYYY-MM-DD format")


def _validate_expires(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expires must be an integer Unix timestamp")
    if value <= 0 or value > _MAX_UNIX_SECONDS:
        raise ValueError("expires must be a valid Unix timestamp")


def _secret_bytes(secret: str | None, environment: str | None) -> bytes:
    resolved = secret if secret is not None else os.environ.get("PREVIEW_SIGNING_SECRET")
    if not resolved:
        raise ValueError("PREVIEW_SIGNING_SECRET is required")
    encoded = resolved.encode("utf-8")
    runtime_environment = environment or os.environ.get("ENVIRONMENT", "production")
    if runtime_environment != "test" and len(encoded) < MIN_NON_TEST_SECRET_BYTES:
        raise ValueError("PREVIEW_SIGNING_SECRET must contain at least 32 bytes")
    return encoded


def generate_preview_signature(
    brief_date: str,
    expires: int,
    *,
    secret: str | None = None,
    environment: str | None = None,
) -> str:
    """Return lowercase HMAC-SHA-256 for ASCII ``date:expires``."""
    _validate_date(brief_date)
    _validate_expires(expires)
    key = _secret_bytes(secret, environment)
    payload = f"{brief_date}:{expires}".encode("ascii")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def build_preview_url(
    brief_date: str,
    expires: int,
    *,
    secret: str | None = None,
    now_seconds: int | None = None,
    environment: str | None = None,
) -> str:
    """Build a relative preview URL whose remaining lifetime is at most 15 minutes."""
    _validate_date(brief_date)
    _validate_expires(expires)
    now = int(time.time()) if now_seconds is None else now_seconds
    _validate_expires(now)
    lifetime = expires - now
    if lifetime <= 0:
        raise ValueError("preview expiry must be in the future")
    if lifetime > MAX_PREVIEW_LIFETIME_SECONDS:
        raise ValueError("preview lifetime must not exceed 900 seconds")
    signature = generate_preview_signature(
        brief_date,
        expires,
        secret=secret,
        environment=environment,
    )
    return f"/preview/{brief_date}?expires={expires}&signature={signature}"
