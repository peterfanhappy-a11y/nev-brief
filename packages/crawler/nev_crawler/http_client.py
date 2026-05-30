"""统一 httpx 客户端工厂 — User-Agent + 超时 + HTTP/2。"""
from __future__ import annotations

import httpx

# 默认对外标识为机器人（合规友好，便于站长溯源）
USER_AGENT = "NEV-Brief-Bot/1.0 (+https://nev-brief.com/about)"

# 浏览器伪装 UA — 仅用于明确拒绝 Bot 的合规来源（如行业协会公开信息）
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)


def make_client(timeout: float = 30.0, user_agent: str | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={
            "User-Agent": user_agent or USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        timeout=httpx.Timeout(timeout, connect=10.0),
        http2=True,
        follow_redirects=True,
    )
