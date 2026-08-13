"""Resend 发送封装（fork 自 nev_delivery.resend_client）。

差异：发件身份走 ai_brief.config（AIVIZENS 趋势）。其余（错误分类、tenacity 重试、
List-Unsubscribe RFC 8058 头、no_proxy_env 隔离 Clash/SOCKS 代理）与 NEV 版一致。
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

from ai_brief.config import FROM_EMAIL, FROM_NAME

log = get_logger("ai_brief.resend")


class ResendError(Exception):
    """Base — 任何 Resend 失败。"""


class ResendAuthError(ResendError):
    """401/403 — fail-fast 不重试。"""


class ResendPermanentError(ResendError):
    """4xx 校验错误（422）— fail-fast。"""


class ResendTransientError(ResendError):
    """5xx / 429 / 网络 — 重试。"""


def _configure_sdk() -> None:
    resend.api_key = get_settings().resend_api_key


def _classify_and_raise(e: resend_exc.ResendError) -> None:
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
    one_click_unsubscribe_url: str,
) -> str:
    """发送一封邮件，返回 Resend email id。"""
    _configure_sdk()
    params: resend.Emails.SendParams = {
        "from": f"{FROM_NAME} <{FROM_EMAIL}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
        "headers": {
            "List-Unsubscribe": f"<{one_click_unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            "Idempotency-Key": idempotency_key,
        },
    }
    try:
        with no_proxy_env():  # resend SDK 走 requests，无 trust_env，需临时清代理
            result = resend.Emails.send(params)
    except resend_exc.ResendError as e:
        _classify_and_raise(e)
        raise  # unreachable
    email_id = result.get("id") if isinstance(result, dict) else None
    if not email_id:
        raise ResendPermanentError(f"Resend returned no id: {result!r}")
    log.info("ai_resend.sent", email_id=email_id)
    return email_id
