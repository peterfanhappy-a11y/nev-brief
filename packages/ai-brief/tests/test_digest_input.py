"""Digest input contract tests — no Gmail credentials or network required."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage
from typing import cast

import pytest
from ai_brief import config
from ai_brief.digest.generate import build_digest_modules
from ai_brief.digest.gmail_input import GmailDigestAdapter
from ai_brief.digest.imap_client import Attachment, DigestEmail, parse_message
from ai_brief.digest.input import DigestKind

BRIEF_DATE = date(2026, 8, 4)
PREFIXES: dict[DigestKind, str] = {
    "events": config.DIGEST_EVENTS_SUBJECT_PREFIX,
    "builder": config.DIGEST_BUILDER_SUBJECT_PREFIX,
    "research": config.DIGEST_RESEARCH_SUBJECT_PREFIX,
    "engineering": config.DIGEST_ENGINEERING_SUBJECT_PREFIX,
    "agent": config.DIGEST_AGENT_SUBJECT_PREFIX,
}


def _email(
    kind: DigestKind,
    subject_date: date = BRIEF_DATE,
    *,
    received_at: datetime | None = None,
    attachments: list[Attachment] | None = None,
) -> DigestEmail:
    return DigestEmail(
        message_id=f"<{kind}@gmail.test>",
        subject=f"{PREFIXES[kind]}{subject_date.isoformat()}",
        date=received_at or datetime(2026, 8, 4, 8, tzinfo=UTC),
        text=f"{kind} plain body",
        html=f"<p>{kind} html body</p>",
        attachments=attachments or [],
    )


def test_fetches_all_five_kinds_as_exact_date_envelopes() -> None:
    """Changing a prefix mapping or exact-match policy must break this contract."""
    emails = {_prefix: _email(kind) for kind, _prefix in PREFIXES.items()}

    def fetcher(sender: str, prefix: str, requested: str | None, **_: object) -> DigestEmail | None:
        assert sender == "digest@example.test"
        assert requested == "2026-08-04"
        return emails[prefix]

    digests = GmailDigestAdapter(sender="digest@example.test", fetcher=fetcher).fetch(BRIEF_DATE)

    assert set(digests) == {"events", "builder", "research", "engineering", "agent"}
    for kind in PREFIXES:
        envelope = digests[kind]
        assert envelope is not None
        assert envelope.kind == kind
        assert envelope.message_id == f"<{kind}@gmail.test>"
        assert envelope.requested_date == BRIEF_DATE
        assert envelope.matched_date == BRIEF_DATE
        assert envelope.used_fallback is False


def test_missing_mail_is_represented_by_none_for_its_kind() -> None:
    """Returning an incomplete mapping would hide missing upstream inputs."""
    digests = GmailDigestAdapter(
        sender="digest@example.test", fetcher=lambda *_args, **_kwargs: None
    ).fetch(BRIEF_DATE)

    assert digests == {
        "events": None,
        "builder": None,
        "research": None,
        "engineering": None,
        "agent": None,
    }


@pytest.mark.parametrize("kind", ["research", "engineering", "agent"])
def test_tool_learning_uses_a_recent_40_hour_fallback_when_exact_date_is_missing(
    kind: DigestKind,
) -> None:
    """Removing the fallback would make date-label drift silently drop research mail."""
    fallback = _email(
        kind,
        date(2026, 8, 5),
        received_at=datetime.now(UTC) - timedelta(hours=1),
    )
    calls: list[tuple[str | None, float | None]] = []

    def fetcher(
        _sender: str, prefix: str, requested: str | None, **kwargs: object
    ) -> DigestEmail | None:
        if prefix != PREFIXES[kind]:
            other_kind = next(
                item_kind for item_kind, value in PREFIXES.items() if value == prefix
            )
            return _email(other_kind)
        calls.append((requested, cast(float | None, kwargs.get("within_hours"))))
        return None if requested else fallback

    digests = GmailDigestAdapter(sender="digest@example.test", fetcher=fetcher).fetch(BRIEF_DATE)

    envelope = digests[kind]
    assert calls == [("2026-08-04", None), (None, 40.0)]
    assert envelope is not None
    assert envelope.matched_date == date(2026, 8, 5)
    assert envelope.used_fallback is True


@pytest.mark.parametrize("kind", ["events", "builder"])
def test_exact_date_kinds_never_fall_back(kind: DigestKind) -> None:
    """Adding fallback to date-sensitive inputs could publish the wrong day's digest."""
    calls: list[tuple[str | None, float | None]] = []

    def fetcher(
        _sender: str, prefix: str, requested: str | None, **kwargs: object
    ) -> DigestEmail | None:
        if prefix == PREFIXES[kind]:
            calls.append((requested, cast(float | None, kwargs.get("within_hours"))))
        return None

    digests = GmailDigestAdapter(sender="digest@example.test", fetcher=fetcher).fetch(BRIEF_DATE)

    assert calls == [("2026-08-04", None)]
    assert digests[kind] is None


def test_tool_learning_rejects_fallback_mail_older_than_40_hours() -> None:
    """Trusting an unbounded IMAP result would publish stale source material."""
    stale = _email(
        "agent",
        date(2026, 8, 1),
        received_at=datetime.now(UTC) - timedelta(hours=41),
    )

    def fetcher(
        _sender: str,
        prefix: str,
        requested: str | None,
        **_: object,
    ) -> DigestEmail | None:
        if prefix == PREFIXES["agent"] and requested is None:
            return stale
        return None

    digests = GmailDigestAdapter(sender="digest@example.test", fetcher=fetcher).fetch(BRIEF_DATE)

    assert digests["agent"] is None


def test_envelope_preserves_attachments_and_serializes_only_safe_metadata() -> None:
    """Run metadata must retain source identity without persisting raw Gmail bodies."""
    attachment = Attachment(filename="hero.png", content_type="image/png", data=b"image-bytes")
    source = _email("events", attachments=[attachment])

    def fetcher(
        _sender: str,
        prefix: str,
        _requested: str | None,
        **_: object,
    ) -> DigestEmail | None:
        return source if prefix == PREFIXES["events"] else None

    envelope = GmailDigestAdapter(sender="digest@example.test", fetcher=fetcher).fetch(
        BRIEF_DATE
    )["events"]

    assert envelope is not None
    assert envelope.attachments == (attachment,)
    assert envelope.metadata() == {
        "kind": "events",
        "message_id": "<events@gmail.test>",
        "subject": "ai-events-digest-2026-08-04",
        "received_at": "2026-08-04T08:00:00+00:00",
        "requested_date": "2026-08-04",
        "matched_date": "2026-08-04",
        "used_fallback": False,
        "attachments": [{"filename": "hero.png", "content_type": "image/png", "size_bytes": 11}],
    }
    metadata_text = str(envelope.metadata())
    assert "events plain body" not in metadata_text
    assert "events html body" not in metadata_text
    assert "image-bytes" not in metadata_text


def test_parse_message_preserves_gmail_message_id() -> None:
    """Dropping Message-ID during MIME parsing would remove source traceability."""
    message = EmailMessage()
    message["Message-ID"] = "<source-message@gmail.test>"
    message["Subject"] = "ai-events-digest-2026-08-04"
    message["Date"] = "Tue, 04 Aug 2026 08:00:00 +0000"
    message.set_content("body")

    assert parse_message(message.as_bytes()).message_id == "<source-message@gmail.test>"


async def test_generation_consumes_envelopes_without_fetching_gmail() -> None:
    """Reintroducing Gmail access inside generation would break the adapter boundary."""
    bundle = await build_digest_modules(
        BRIEF_DATE,
        dict.fromkeys(PREFIXES),
    )

    assert bundle.today_ai is None
    assert bundle.ai_masters is None
    assert bundle.ai_research is None
    assert bundle.ai_engineering is None
    assert bundle.agent_tools is None
