"""robots.txt 检查器 + per-host 缓存。"""
from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from nev_shared.logger import get_logger

log = get_logger("robots")


class RobotsChecker:
    def __init__(self, user_agent: str = "NEV-Brief-Bot/1.0", timeout: float = 10.0):
        self._user_agent = user_agent
        self._timeout = timeout
        self._cache: dict[str, RobotFileParser] = {}

    async def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        host_key = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._cache.get(host_key)
        if rp is None:
            rp = await self._fetch(host_key)
            self._cache[host_key] = rp
        return rp.can_fetch(self._user_agent, url)

    async def _fetch(self, host_key: str) -> RobotFileParser:
        url = f"{host_key}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(url)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    # 404 或其他 → 默认允许（行业惯例）
                    rp.parse([])
                    log.info("robots_unavailable", host=host_key, status=resp.status_code)
        except Exception as exc:  # noqa: BLE001
            log.warning("robots_fetch_failed", host=host_key, error=str(exc))
            rp.parse([])  # 失败也默认允许，但记日志
        return rp
