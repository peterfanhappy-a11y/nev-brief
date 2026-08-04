"""Gmail-backed implementation of the digest input contract."""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from ai_brief import config
from ai_brief.digest.imap_client import DigestEmail, _date_key, fetch_latest
from ai_brief.digest.input import DigestEnvelope, DigestKind

FetchDigestEmail = Callable[..., DigestEmail | None]

_SUBJECT_PREFIXES: dict[DigestKind, str] = {
    "events": config.DIGEST_EVENTS_SUBJECT_PREFIX,
    "builder": config.DIGEST_BUILDER_SUBJECT_PREFIX,
    "research": config.DIGEST_RESEARCH_SUBJECT_PREFIX,
    "engineering": config.DIGEST_ENGINEERING_SUBJECT_PREFIX,
    "agent": config.DIGEST_AGENT_SUBJECT_PREFIX,
}
_FALLBACK_KINDS: frozenset[DigestKind] = frozenset(
    {"research", "engineering", "agent"}
)
_FALLBACK_HOURS = 40.0


def _subject_date(subject: str) -> date | None:
    parts = _date_key(subject)
    if parts is None:
        return None
    try:
        return date(*parts)
    except ValueError:
        return None


def _is_recent(email: DigestEmail, *, hours: float) -> bool:
    received_at = email.date
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    return received_at >= datetime.now(UTC) - timedelta(hours=hours)


class GmailDigestAdapter:
    def __init__(
        self,
        *,
        sender: str | None = None,
        fetcher: FetchDigestEmail = fetch_latest,
    ) -> None:
        self._sender = sender or config.digest_sender()
        self._fetcher = fetcher

    def fetch(self, brief_date: date) -> dict[DigestKind, DigestEnvelope | None]:
        requested = brief_date.isoformat()
        digests: dict[DigestKind, DigestEnvelope | None] = {}
        for kind, prefix in _SUBJECT_PREFIXES.items():
            email = self._fetcher(self._sender, prefix, requested)
            used_fallback = False
            if email is None and kind in _FALLBACK_KINDS:
                email = self._fetcher(
                    self._sender,
                    prefix,
                    None,
                    within_hours=_FALLBACK_HOURS,
                )
                used_fallback = email is not None
                if email is not None and not _is_recent(email, hours=_FALLBACK_HOURS):
                    email = None
                    used_fallback = False

            digests[kind] = (
                _envelope(kind, email, brief_date, used_fallback)
                if email is not None
                else None
            )
        return digests


def _envelope(
    kind: DigestKind,
    email: DigestEmail,
    requested_date: date,
    used_fallback: bool,
) -> DigestEnvelope:
    return DigestEnvelope(
        kind=kind,
        message_id=email.message_id,
        subject=email.subject,
        received_at=email.date,
        requested_date=requested_date,
        matched_date=_subject_date(email.subject),
        used_fallback=used_fallback,
        text=email.text,
        html=email.html,
        attachments=tuple(email.attachments),
    )
