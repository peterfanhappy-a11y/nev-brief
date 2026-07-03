"""Deliverer — 排空 ai_deliveries 的 pending 队列。

每行独立 commit（一封坏邮件不回滚其余）：claim → send → mark_sent/failed/reset → commit。
subject 从行内读（每日动态）；幂等键 ai-{date}-{sub}；退订 URL 带 &product=ai。
"""
from __future__ import annotations

from dataclasses import dataclass

import psycopg
from nev_shared.logger import get_logger

from ai_brief import config, storage
from ai_brief.resend_client import (
    ResendAuthError,
    ResendPermanentError,
    ResendTransientError,
    send_email,
)
from ai_brief.storage import PendingAiDelivery

log = get_logger("ai_brief.deliverer")


@dataclass(frozen=True)
class SendResult:
    attempted: int
    sent: int
    failed: int


def _send_one(conn: psycopg.Connection, d: PendingAiDelivery) -> bool:
    idempotency_key = f"ai-{d.brief_date.isoformat()}-{d.subscriber_id}"
    unsub_url = f"{config.UNSUBSCRIBE_PREFIX}{d.unsubscribe_token}&product=ai"

    try:
        email_id = send_email(
            to=d.email,
            subject=d.subject,
            html=d.content_html,
            text=d.content_text,
            idempotency_key=idempotency_key,
            unsubscribe_url=unsub_url,
        )
    except (ResendAuthError, ResendPermanentError) as e:
        log.error("ai_send.permanent_failure", delivery_id=d.delivery_id, email=d.email, error=str(e))
        storage.mark_failed(conn, delivery_id=d.delivery_id, error=str(e))
        conn.commit()
        return False
    except ResendTransientError as e:
        log.warning("ai_send.transient_failure", delivery_id=d.delivery_id, email=d.email, error=str(e))
        storage.reset_to_pending(conn, delivery_id=d.delivery_id, error=str(e))
        conn.commit()
        return False
    except Exception as e:  # noqa: BLE001 — defensive
        log.exception("ai_send.unexpected_error", delivery_id=d.delivery_id)
        storage.mark_failed(conn, delivery_id=d.delivery_id, error=f"unexpected: {e!r}")
        conn.commit()
        return False

    storage.mark_sent(conn, delivery_id=d.delivery_id, resend_email_id=email_id)
    conn.commit()
    log.info("ai_send.ok", delivery_id=d.delivery_id, email=d.email, resend_id=email_id)
    return True


def send_pending(conn: psycopg.Connection, *, limit: int = 200) -> SendResult:
    """排空至多 limit 封 pending 投递。每行独立 commit。"""
    pendings = storage.claim_pending_deliveries(conn, limit=limit)
    if not pendings:
        return SendResult(attempted=0, sent=0, failed=0)
    conn.commit()  # 释放 claim 锁，后续可逐行独立 commit

    sent = failed = 0
    for d in pendings:
        if _send_one(conn, d):
            sent += 1
        else:
            failed += 1
    log.info("ai_deliverer.done", attempted=len(pendings), sent=sent, failed=failed)
    return SendResult(attempted=len(pendings), sent=sent, failed=failed)
