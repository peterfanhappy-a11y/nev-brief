"""统一 httpx 客户端工厂 — User-Agent + 超时 + HTTP/2。"""
from __future__ import annotations

import httpx

USER_AGENT = "NEV-Brief-Bot/1.0 (+https://nev-brief.com/about)"


def make_client(timeout: float = 30.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
        timeout=httpx.Timeout(timeout, connect=10.0),
        http2=True,
        follow_redirects=True,
    )
