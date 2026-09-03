"""imap_client.parse_message —— MIME 解析纯函数测试（不触网）。"""
from __future__ import annotations

import imaplib
from datetime import UTC, datetime, timedelta, timezone
from email.message import EmailMessage
from unittest.mock import patch

import ai_brief.digest.imap_client as imap_client
import pytest
from ai_brief.digest.imap_client import fetch_latest, parse_message


def _raw_email(
    *,
    subject: str,
    message_id: str,
    date_header: str | None,
) -> bytes:
    headers = [
        f"Subject: {subject}",
        "From: digest@example.test",
        "To: reader@example.test",
        f"Message-ID: {message_id}",
    ]
    if date_header is not None:
        headers.append(f"Date: {date_header}")
    return ("\r\n".join(headers) + "\r\n\r\nbody").encode()


class _FakeIMAP:
    def __init__(self, records: list[tuple[datetime, bytes]]) -> None:
        self._records = {
            str(index).encode(): record
            for index, record in enumerate(records, start=1)
        }

    def login(self, _user: str, _password: str) -> None:
        return None

    def select(self, _mailbox: str, *, readonly: bool) -> None:
        assert readonly is True

    def search(self, *_args: object) -> tuple[str, list[bytes]]:
        return "OK", [b" ".join(self._records)]

    def fetch(self, uid: bytes, query: str) -> tuple[str, list[tuple[bytes, bytes]]]:
        received_at, raw = self._records[uid]
        if "HEADER.FIELDS" in query:
            fields = raw.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
            attributes = [uid + b" ("]
            if "INTERNALDATE" in query:
                stamp = received_at.strftime("%d-%b-%Y %H:%M:%S %z").encode()
                attributes.append(b'INTERNALDATE "' + stamp + b'" ')
            attributes.append(b"BODY[HEADER.FIELDS] {" + str(len(fields)).encode() + b"}")
            return "OK", [(b"".join(attributes), fields)]
        assert query == "(RFC822)"
        return "OK", [(uid + b" (RFC822 {" + str(len(raw)).encode() + b"}", raw)]

    def logout(self) -> None:
        return None


def _build_raw() -> bytes:
    msg = EmailMessage()
    msg["Subject"] = "ai-events-digest-2026-07-06"
    msg["From"] = "paul.fan.2200@gmail.com"
    msg["To"] = "peter.fan.happy@gmail.com"
    msg["Date"] = "Sun, 06 Jul 2026 06:11:21 +0800"
    msg.set_content("纯文本兜底")
    msg.add_alternative("<h2>今日AI</h2><p>正文</p>", subtype="html")
    msg.add_attachment(
        b"\x89PNG\r\n\x1a\n-fake-01", maintype="image", subtype="png",
        filename="01-anthropic-sonnet5.png",
    )
    msg.add_attachment(
        b"\x89PNG\r\n\x1a\n-fake-02", maintype="image", subtype="png",
        filename="02-baidu-wenxin5.png",
    )
    return msg.as_bytes()


def test_parse_extracts_html_text_and_images() -> None:
    d = parse_message(
        _build_raw(),
        received_at=datetime(2026, 7, 6, 0, tzinfo=UTC),
    )
    assert d.subject == "ai-events-digest-2026-07-06"
    assert d.html and "今日AI" in d.html
    assert d.text and "纯文本兜底" in d.text
    imgs = d.image_attachments()
    assert [a.filename for a in imgs] == ["01-anthropic-sonnet5.png", "02-baidu-wenxin5.png"]
    assert imgs[0].content_type == "image/png"
    assert imgs[0].data.endswith(b"-fake-01")


def test_parse_date_parsed_with_tz() -> None:
    received_at = datetime(2026, 7, 6, 0, tzinfo=UTC)

    d = parse_message(_build_raw(), received_at=received_at)

    assert d.sent_at is not None
    assert d.sent_at.year == 2026 and d.sent_at.month == 7 and d.sent_at.day == 6
    assert d.sent_at.tzinfo is not None
    assert d.received_at == received_at


@pytest.mark.parametrize("date_header", [None, "not-a-real-date"])
def test_fetch_latest_ranks_by_internaldate_not_rfc_date(
    date_header: str | None,
) -> None:
    """A future sender Date must not outrank a genuinely newer Gmail receipt."""
    now = datetime.now(UTC)
    old_received = now - timedelta(hours=20)
    recent_received = now - timedelta(hours=1)
    future_sent = "Tue, 04 Aug 2099 08:00:00 +0000"
    fake = _FakeIMAP(
        [
            (
                old_received,
                _raw_email(
                    subject="ai-research-digest-2026-08-04",
                    message_id="<future-sent@gmail.test>",
                    date_header=future_sent,
                ),
            ),
            (
                recent_received,
                _raw_email(
                    subject="ai-research-digest-2026-08-04",
                    message_id="<recently-received@gmail.test>",
                    date_header=date_header,
                ),
            ),
        ]
    )

    with patch.object(imap_client, "_connect", return_value=fake):
        result = fetch_latest(
            "digest@example.test",
            "ai-research-digest-",
            None,
            user="test-user",
            password="test-password",  # noqa: S106 - isolated fake IMAP credential
            within_hours=40,
        )

    assert result is not None
    assert result.message_id == "<recently-received@gmail.test>"
    assert result.received_at == recent_received.replace(microsecond=0)


@pytest.mark.parametrize("date_header", [None, "not-a-real-date"])
def test_fetch_latest_rejects_old_internaldate_despite_missing_or_bad_rfc_date(
    date_header: str | None,
) -> None:
    """Missing or malformed sender dates must not refresh stale Gmail receipts."""
    fake = _FakeIMAP(
        [
            (
                datetime.now(UTC) - timedelta(hours=41),
                _raw_email(
                    subject="ai-agent-digest-2026-08-04",
                    message_id="<stale@gmail.test>",
                    date_header=date_header,
                ),
            )
        ]
    )

    with patch.object(imap_client, "_connect", return_value=fake):
        result = fetch_latest(
            "digest@example.test",
            "ai-agent-digest-",
            None,
            user="test-user",
            password="test-password",  # noqa: S106 - isolated fake IMAP credential
            within_hours=40,
        )

    assert result is None


def test_fetch_latest_keeps_exact_subject_date_matching_with_internaldate() -> None:
    """Switching the ordering clock must not loosen exact subject-date selection."""
    now = datetime.now(UTC)
    fake = _FakeIMAP(
        [
            (
                now - timedelta(minutes=1),
                _raw_email(
                    subject="ai-events-digest-2026-08-05",
                    message_id="<wrong-subject-date@gmail.test>",
                    date_header="Wed, 05 Aug 2026 08:00:00 +0000",
                ),
            ),
            (
                now - timedelta(hours=2),
                _raw_email(
                    subject="ai-events-digest-2026-08-04",
                    message_id="<exact-subject-date@gmail.test>",
                    date_header="Tue, 04 Aug 2026 08:00:00 +0000",
                ),
            ),
        ]
    )

    with patch.object(imap_client, "_connect", return_value=fake):
        result = fetch_latest(
            "digest@example.test",
            "ai-events-digest-",
            "2026-08-04",
            user="test-user",
            password="test-password",  # noqa: S106 - isolated fake IMAP credential
        )

    assert result is not None
    assert result.message_id == "<exact-subject-date@gmail.test>"
    assert result.received_at == (now - timedelta(hours=2)).replace(microsecond=0)


def test_fetch_latest_preserves_negative_internaldate_timezone_offset() -> None:
    """Parsing INTERNALDATE must not turn a negative timezone into a positive one."""
    received_at = datetime(
        2026,
        8,
        4,
        8,
        tzinfo=timezone(-timedelta(hours=7)),
    )
    fake = _FakeIMAP(
        [
            (
                received_at,
                _raw_email(
                    subject="ai-events-digest-2026-08-04",
                    message_id="<negative-offset@gmail.test>",
                    date_header=None,
                ),
            )
        ]
    )

    with patch.object(imap_client, "_connect", return_value=fake):
        result = fetch_latest(
            "digest@example.test",
            "ai-events-digest-",
            "2026-08-04",
            user="test-user",
            password="test-password",  # noqa: S106 - isolated fake IMAP credential
        )

    assert result is not None
    assert result.received_at == datetime(2026, 8, 4, 15, tzinfo=UTC)


def test_fetch_latest_retries_one_imap_abort_then_returns_email() -> None:
    received_at = datetime.now(UTC) - timedelta(minutes=1)
    fake = _FakeIMAP(
        [
            (
                received_at,
                _raw_email(
                    subject="ai-events-digest-2026-08-04",
                    message_id="<retry@gmail.test>",
                    date_header="Tue, 04 Aug 2026 08:00:00 +0000",
                ),
            )
        ]
    )

    with patch.object(
        imap_client,
        "_connect",
        side_effect=[imaplib.IMAP4.abort("socket error: EOF"), fake],
    ):
        result = fetch_latest(
            "digest@example.test",
            "ai-events-digest-",
            "2026-08-04",
            user="test-user",
            password="test-password",  # noqa: S106 - isolated fake IMAP credential
        )

    assert result is not None
    assert result.message_id == "<retry@gmail.test>"


def test_fetch_latest_retries_transient_connection_failures_before_returning_email() -> None:
    received_at = datetime.now(UTC) - timedelta(minutes=1)
    fake = _FakeIMAP(
        [
            (
                received_at,
                _raw_email(
                    subject="ai-events-digest-2026-08-04",
                    message_id="<third-attempt@gmail.test>",
                    date_header="Tue, 04 Aug 2026 08:00:00 +0000",
                ),
            )
        ]
    )

    with patch.object(
        imap_client,
        "_connect",
        side_effect=[
            imaplib.IMAP4.abort("socket error: EOF"),
            OSError("TLS connection reset"),
            fake,
        ],
    ):
        result = fetch_latest(
            "digest@example.test",
            "ai-events-digest-",
            "2026-08-04",
            user="test-user",
            password="test-password",  # noqa: S106 - isolated fake IMAP credential
        )

    assert result is not None
    assert result.message_id == "<third-attempt@gmail.test>"
