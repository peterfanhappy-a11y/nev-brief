"""飞书 webhook client tests — mocked httpx."""
from __future__ import annotations

import httpx
import pytest
import respx
from nev_shared.feishu import AlertLevel, send_alert


@respx.mock
def test_send_alert_posts_correct_payload(monkeypatch):
    """P1 alert posts a feishu-shaped JSON to the webhook URL."""
    url = "https://open.feishu.cn/open-apis/bot/v2/hook/test-token"
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", url)
    from nev_shared.config import get_settings
    get_settings.cache_clear()

    route = respx.post(url).mock(return_value=httpx.Response(200, json={"code": 0, "msg": "ok"}))

    send_alert(level=AlertLevel.P1, title="Crawler 失败", body="domain example.com 全 404")

    assert route.called
    request = route.calls[0].request
    payload = request.read().decode("utf-8")
    assert '"msg_type": "text"' in payload
    assert "[P1] Crawler 失败" in payload
    assert "domain example.com" in payload


@respx.mock
def test_send_alert_swallows_http_errors(monkeypatch):
    """If webhook is down, alert must NOT raise."""
    url = "https://open.feishu.cn/open-apis/bot/v2/hook/test-token"
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", url)
    from nev_shared.config import get_settings
    get_settings.cache_clear()

    respx.post(url).mock(side_effect=httpx.ConnectError("dns fail"))

    # Should NOT raise
    send_alert(level=AlertLevel.P0, title="DB down", body="psycopg connect failed")


def test_alert_level_values():
    assert AlertLevel.P0.value == "P0"
    assert AlertLevel.P1.value == "P1"
    assert AlertLevel.P2.value == "P2"
    assert AlertLevel.INFO.value == "INFO"
