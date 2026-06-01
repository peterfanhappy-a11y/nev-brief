"""Delivery sender — main loop that drains pending deliveries.

Per-delivery commit pattern (one bad row doesn't roll back the rest):
    claim → send → mark_sent OR mark_failed/reset → commit
"""
from __future__ import annotations

from dataclasses import dataclass

import psycopg
from nev_shared.logger import get_logger

from nev_delivery.config import LIST_UNSUBSCRIBE_PREFIX
from nev_delivery.resend_client import (
    ResendAuthError,
    ResendPermanentError,
    ResendTransientError,
    send_email,
)
from nev_delivery.storage import (
    PendingDelivery,
    claim_pending_deliveries,
    mark_failed,
    mark_sent,
    reset_to_pending,
)

log = get_logger("delivery.sender")


@dataclass(frozen=True)
class SendResult:
    attempted: int
    sent: int
    failed: int


def _subject_for(d: PendingDelivery) -> str:
    return f"【NEV 早报】{d.brief_date.isoformat()} · 10 条新闻"


def _send_one(conn: psycopg.Connection, d: PendingDelivery) -> bool:
    """Send one delivery. Returns True if sent, False if failed/queued.

    Per-row commit/rollback contained here.
    """
    idempotency_key = f"nev-{d.brief_date.isoformat()}-{d.subscriber_id}"
    unsub_url = f"{LIST_UNSUBSCRIBE_PREFIX}{d.unsubscribe_token}"
    subject = _subject_for(d)

    try:
        email_id = send_email(
            to=d.email,
            subject=subject,
            html=d.content_html,
            text=d.content_text,
            idempotency_key=idempotency_key,
            unsubscribe_url=unsub_url,
        )
    except (ResendAuthError, ResendPermanentError) as e:
        log.error("send.permanent_failure", delivery_id=d.delivery_id,
                  email=d.email, error=str(e))
        mark_failed(conn, delivery_id=d.delivery_id, error=str(e))
        conn.commit()
        return False
    except ResendTransientError as e:
        log.warning("send.transient_failure", delivery_id=d.delivery_id,
                    email=d.email, error=str(e))
        reset_to_pending(conn, delivery_id=d.delivery_id, error=str(e))
        conn.commit()
        return False
    except Exception as e:  # noqa: BLE001 — defensive
        log.exception("send.unexpected_error", delivery_id=d.delivery_id)
        mark_failed(conn, delivery_id=d.delivery_id, error=f"unexpected: {e!r}")
        conn.commit()
        return False

    mark_sent(conn, delivery_id=d.delivery_id, resend_email_id=email_id)
    conn.commit()
    log.info("send.ok", delivery_id=d.delivery_id, email=d.email, resend_id=email_id)
    return True


def send_pending(conn: psycopg.Connection, *, limit: int = 50) -> SendResult:
    """Drain up to `limit` pending deliveries.

    Each row claimed in 'sending' state; status flips to 'sent' / 'failed' /
    back to 'pending' at end. Per-row commit isolates failures.
    """
    pendings = claim_pending_deliveries(conn, limit=limit)
    if not pendings:
        return SendResult(attempted=0, sent=0, failed=0)
    conn.commit()  # release the claim lock so we can commit each row independently

    sent = 0
    failed = 0
    for d in pendings:
        if _send_one(conn, d):
            sent += 1
        else:
            failed += 1
    return SendResult(attempted=len(pendings), sent=sent, failed=failed)
