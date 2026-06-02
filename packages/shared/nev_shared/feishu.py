"""飞书自定义机器人 webhook — P0/P1/P2 告警通道。

Spec §7.4: 飞书 = P0/P1 即时；P2 累积每日 9:00 汇总。
MVP 只发即时消息；P2 汇总由后续 monitor 单独实现。

设计原则：alert 函数永不抛异常 — 告警失败不应级联击垮主流程。
"""
from __future__ import annotations

import json
from enum import Enum

import httpx
from nev_shared.config import get_settings
from nev_shared.logger import get_logger

log = get_logger("feishu")


class AlertLevel(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    INFO = "INFO"


def _build_payload(level: AlertLevel, title: str, body: str) -> dict:
    return {
        "msg_type": "text",
        "content": {"text": f"[{level.value}] {title}\n\n{body}"},
    }


def send_alert(*, level: AlertLevel, title: str, body: str) -> None:
    """发送告警到飞书。永不抛异常 — 告警失败仅记录。"""
    settings = get_settings()
    webhook_url = settings.feishu_webhook_url
    if not webhook_url:
        log.warning("feishu.disabled", level=level.value, title=title)
        return

    payload = _build_payload(level, title, body)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                webhook_url,
                content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            resp.raise_for_status()
        log.info("feishu.sent", level=level.value, title=title)
    except Exception as e:  # noqa: BLE001 — alert MUST NOT raise
        log.error("feishu.failed", level=level.value, title=title, error=str(e))
