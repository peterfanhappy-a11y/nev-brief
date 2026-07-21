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


# ── 工具学习板块（AI研究 / AI工程 / Agent工具）─────────────────────────


@dataclass
class ResearchPaper:
    """ai-research-digest 里的一篇论文（AI研究 模块）。"""

    source_tag: str          # 来源标签，如「Arxiv」「HuggingFace」→ 与附件名匹配
    title: str               # 中文标题（去掉英文括注）
    takeaways: list[str]     # Core Takeaways 三条
    url: str                 # 原文链接

    def matches_filename(self, filename: str) -> bool:
        """附件名（arxiv.png / huggingface.png）是否属于本篇来源。"""
        tag = (self.source_tag or "").lower().replace(" ", "")
        name = (filename or "").lower()
        return bool(tag) and tag in name


@dataclass
class CorePoint:
    """AI工程 核心要点的一条：加粗小标题 + 正文。"""

    subtitle: str
    body: str


@dataclass
class EngineeringLecture:
    """ai-engineering-digest 里的一讲（AI工程 模块）。"""

    lecture_no: int          # 第 N 讲（0=未知）
    source_title: str        # 来源课程名（不展示链接，仅留档）
    source_url: str
    key_point: str           # 💡 课程要点（一句话）→ 模块主题
    core_points: list[CorePoint]  # 📋 核心要点（多条）→ 模块内容


@dataclass
class AgentTool:
    """ai-agent-digest 里的一个工具（Agent工具 模块，共 3 个选 2 个）。"""

    rank: int                # 1/2/3（榜单序）
    name: str                # 「mattpocock/skills — 真实工程AI编程技能集」
    stars: str               # 「10,983」本周 star 数（展示用字符串）
    points: list[str]        # 3 要点总结
    url: str                 # GitHub 仓库链接
