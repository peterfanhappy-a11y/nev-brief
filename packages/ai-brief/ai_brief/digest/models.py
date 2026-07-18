"""Digest 解析后的中间数据结构（未经 DeepSeek 压缩 / 选图）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EventItem:
    """ai-events-digest 里的一条新闻（今日AI 模块，共 3 条）。"""

    index: int          # 1-based，对应附件序号前缀 01/02/03
    category: str       # 分类标签，如「海外大模型」
    value_tag: str      # 价值标签，如「最有价值」「🔥 地缘冲突」
    headline: str
    url: str
    body: str           # 原始长正文（未压缩）
    image_note: str     # 「🖼️ 头图：…」说明文字（去掉前缀）

    @property
    def label(self) -> str:
        """展示用组合标签：分类 · 价值。"""
        parts = [p for p in (self.category, self.value_tag) if p]
        return " · ".join(parts)


@dataclass
class BuilderItem:
    """follow-builder-digest 里的一条（AI大神 模块，共 10 条）。"""

    index: int          # 1-based
    is_top5: bool       # True=前5(★)，False=后5(🔥)
    person: str         # 方括号里的人名/来源，如「Cloudflare CEO Matthew Prince」
    headline: str
    body: str           # 原始正文（未压缩）
    url: str

    @property
    def has_image(self) -> bool:
        """仅 [6]-[10] 带 tweet 附件。"""
        return not self.is_top5
