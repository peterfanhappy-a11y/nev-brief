"""Deliverer — 排空 ai_deliveries 的 pending 队列。

每行独立 commit（一封坏邮件不回滚其余）：claim → send → mark_sent/failed/reset → commit。
subject 从行内读（每日动态）；幂等键 ai-{date}-{sub}；RFC 8058 header 指向 API。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

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
    # Hold the subscriber row lock through the external send. An unsubscribe that
    # committed first is respected; one that begins after transport starts waits
    # until this delivery has reached a terminal state.
    if not storage.lock_active_subscriber(conn, subscriber_id=d.subscriber_id):
        storage.mark_suppressed(conn, delivery_id=d.delivery_id)
        conn.commit()
        log.info("ai_send.suppressed_inactive", delivery_id=d.delivery_id)
        return False

    # 生产用 ai-{date}-{sub}（每订阅者每日唯一，防重发）。测试当天想重发看新版时，
    # 设 AI_IDEMPOTENCY_SUFFIX=v2 拿到新 key 绕过 Resend 24h 去重。
    suffix = os.environ.get("AI_IDEMPOTENCY_SUFFIX", "")
    idempotency_key = (
        f"ai-{d.brief_date.isoformat()}-{d.subscriber_id}"
        f"{('-' + suffix) if suffix else ''}"
    )
    one_click_unsub_url = (
        f"{config.WEB_BASE_URL}/api/unsubscribe"
        f"?token={d.unsubscribe_token}&product=ai"
    )

    try:
        email_id = send_email(
            to=d.email,
            subject=d.subject,
            html=d.content_html,
            text=d.content_text,
            idempotency_key=idempotency_key,
            one_click_unsubscribe_url=one_click_unsub_url,
        )
    except (ResendAuthError, ResendPermanentError) as e:
        log.error(
            "ai_send.permanent_failure",
            delivery_id=d.delivery_id,
            error_type=type(e).__name__,
        )
        storage.mark_failed(conn, delivery_id=d.delivery_id, error=str(e))
        conn.commit()
        return False
    except ResendTransientError as e:
        log.warning(
            "ai_send.transient_failure",
            delivery_id=d.delivery_id,
            error_type=type(e).__name__,
        )
        storage.reset_to_pending(
            conn,
            delivery_id=d.delivery_id,
            error=f"transient:{type(e).__name__}",
        )
        conn.commit()
        return False
    except Exception as e:  # noqa: BLE001 — defensive
        log.error(
            "ai_send.unexpected_error",
            delivery_id=d.delivery_id,
            error_type=type(e).__name__,
        )
        storage.mark_failed(conn, delivery_id=d.delivery_id, error=f"unexpected: {e!r}")
        conn.commit()
        return False

    storage.mark_sent(conn, delivery_id=d.delivery_id, resend_email_id=email_id)
    conn.commit()
    log.info("ai_send.ok", delivery_id=d.delivery_id, resend_id=email_id)
    return True


def send_pending(
    conn: psycopg.Connection,
    *,
    limit: int = 200,
    brief_date: date | None = None,
    retry_transient: bool = False,
) -> SendResult:
    """排空至多 limit 封 pending 投递。每行独立 commit。"""
    if retry_transient:
        storage.retry_transient_deliveries(conn, brief_date=brief_date)
        conn.commit()
    pendings = storage.claim_pending_deliveries(conn, limit=limit, brief_date=brief_date)
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
