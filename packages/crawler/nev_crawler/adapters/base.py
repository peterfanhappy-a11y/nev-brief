"""Adapter 抽象基类 — 所有具体 adapter 实现 fetch()。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from python.content import ArticleRaw


@dataclass
class FetchResult:
    """单次 fetch 的产出 — 包括成功条目与错误信息。"""

    articles: list[ArticleRaw] = field(default_factory=list)
    error: str | None = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def ok(self) -> bool:
        return self.error is None


class Adapter(ABC):
    """所有具体 adapter（rss/html/api/rsshub）继承此类。

    每个 adapter 单一职责：拉取 + 解析 + 返回 ArticleRaw 列表。
    不负责入库（由 storage.py 完成）；不负责重试/限速（由 runner.py 编排）。
    """

    type_name: str = "base"

    @abstractmethod
    async def fetch(self, source: dict[str, Any]) -> FetchResult:
        """source 是 sources 表一行（dict），包含 url / extra 等字段。"""
        ...
