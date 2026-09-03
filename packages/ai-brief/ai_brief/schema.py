"""AiBriefContent — 每日简报文档的 pydantic schema（单一来源）。

Stage-2 DeepSeek 输出经此校验后存入 ai_daily_briefs.content jsonb。
校验点：字数上限、必填板块、theme 枚举、URL 白名单（在 summarizer 里代码层强制，
schema 只保证结构）。所有 max_length 是软约束——超限时 summarizer 触发重试/截断。
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION: Literal[1] = 1

BriefStatus = Literal[
    "generating",
    "blocked",
    "awaiting_approval",
    "approved",
    "published",
]

# Shared by the pure quality gate and the fail-closed persistence boundary. Keep
# this catalog structural: arbitrary model/source text must never become a key,
# code, or path accepted by storage.
QUALITY_ISSUE_CODES = frozenset(
    {
        "agent_tool_story_count_below_minimum",
        "ai_masters_story_count_below_minimum",
        "brief_status_protected",
        "critical_url_missing",
        "deepseek_incomplete",
        "digest_date_fallback",
        "editorial_blank",
        "intro_blank",
        "non_core_items_filtered",
        "parse_failed",
        "placeholder_url",
        "qwen_image_fallback",
        "required_digest_stale",
        "schema_invalid",
        "source_domain_unknown",
        "subject_blank",
        "summary_near_limit",
        "today_ai_story_count_below_minimum",
        "today_ai_region_quota_invalid",
        "tool_module_count_below_minimum",
        "tool_module_missing",
        "url_not_https",
    }
)
QUALITY_METRIC_KEYS = frozenset(
    {
        "agent_freshness_hours",
        "agent_story_count",
        "ai_masters_story_count",
        "blocker_count",
        "builder_freshness_hours",
        "deepseek_complete",
        "digest_date_fallback",
        "editorial_length",
        "engineering_freshness_hours",
        "engineering_story_count",
        "events_freshness_hours",
        "existing_brief_protected",
        "filtered_non_core_item_count",
        "intro_bullet_count",
        "max_digest_freshness_hours",
        "missing_tool_module_count",
        "parsed_items",
        "quality_passed",
        "qwen_complete",
        "qwen_image_fallback",
        "required_digests_fresh",
        "research_freshness_hours",
        "research_story_count",
        "schema_valid",
        "subject_length",
        "summary_near_limit_count",
        "today_ai_story_count",
        "tool_module_count",
        "unknown_source_domain_count",
        "warning_count",
    }
)
QUALITY_BRIEF_PATHS = frozenset(
    {"editorial", "intro_bullets", "preheader", "subject"}
)
QUALITY_DIGEST_SECTION_ROOTS = frozenset(
    {"agent_tools", "ai_engineering", "ai_masters", "ai_research", "today_ai"}
)
QUALITY_DIGEST_SECTION_FIELDS = frozenset(
    {"cta_label", "header_image", "header_image_alt", "stories", "subtitle", "theme"}
)
QUALITY_DIGEST_STORY_FIELDS = frozenset({"headline", "label", "summary", "url"})
QUALITY_DIGEST_SOURCE_KINDS = frozenset(
    {"agent", "builder", "engineering", "events", "research"}
)
QUALITY_DIGEST_SOURCE_FIELDS = frozenset(
    {"matched_date", "received_at", "requested_date", "used_fallback"}
)
_QUALITY_INDEXED_STORY_PATH = re.compile(
    r"^stories\[(?:0|[1-9][0-9]*)\](?:\.([a-z_]+))?$"
)


def quality_path_is_allowed(path: str) -> bool:
    """Return whether a structural issue path is safe for run persistence."""
    if path in QUALITY_BRIEF_PATHS or path in QUALITY_DIGEST_SECTION_ROOTS:
        return True

    root, separator, remainder = path.partition(".")
    if not separator:
        return False
    if root == "digests":
        kind, field_separator, field = remainder.partition(".")
        return kind in QUALITY_DIGEST_SOURCE_KINDS and (
            not field_separator or field in QUALITY_DIGEST_SOURCE_FIELDS
        )
    if root not in QUALITY_DIGEST_SECTION_ROOTS:
        return False
    if remainder in QUALITY_DIGEST_SECTION_FIELDS:
        return True
    story_match = _QUALITY_INDEXED_STORY_PATH.fullmatch(remainder)
    return story_match is not None and (
        story_match.group(1) is None
        or story_match.group(1) in QUALITY_DIGEST_STORY_FIELDS
    )


class Theme(str, Enum):  # noqa: UP042 - preserve legacy str(Enum) behavior
    MODEL_RESEARCH = "model_research"
    PRODUCT_TOOLS = "product_tools"
    SKILLS_EFFICIENCY = "skills_efficiency"
    ETHICS_REGULATION = "ethics_regulation"
    # 工具学习板块
    AI_RESEARCH = "ai_research"
    AI_ENGINEERING = "ai_engineering"
    AGENT_TOOLS = "agent_tools"


class FeaturedItem(BaseModel):
    theme: Theme
    theme_label: str
    headline: str = Field(max_length=40)
    details: list[str] = Field(min_length=1, max_length=5)
    significance: str = Field(max_length=160)
    url: str
    source_name: str
    og_image: str | None = None
    article_id: str | None = None  # ai_articles.id 溯源


class DigestStory(BaseModel):
    """digest 模块（今日AI/AI大神）里的一条新闻。正文已由 DeepSeek 压缩。"""

    headline: str = Field(max_length=80)
    summary: str = Field(max_length=260)  # 今日AI≤150 / AI大神≤120 / AI研究≤200（软约束）
    url: str = ""  # AI工程 核心要点无链接 → 允许空
    label: str = ""  # 分类·价值（今日AI）或 人名/来源（AI大神）或 ⭐stars（Agent工具）


class DigestSection(BaseModel):
    """一个 digest 驱动的模块：1 张头图 + 可选主题句 + 多条 story。"""

    theme: Theme
    header_image: str | None = None       # 已转存的 Supabase Storage 公开 URL
    header_image_alt: str = ""
    subtitle: str = ""                    # 模块主题句（AI工程=课程要点；其余留空）
    cta_label: str = "阅读原文"           # story 链接文案（AI研究=阅读论文 / Agent工具=查看仓库）
    stories: list[DigestStory] = Field(min_length=1, max_length=6)


class Tool(BaseModel):
    name: str = Field(max_length=40)
    one_liner: str = Field(max_length=60)
    url: str


class DailyTip(BaseModel):
    title: str = Field(max_length=30)
    body: str = Field(max_length=260)


class QuickHit(BaseModel):
    text: str = Field(max_length=80)
    url: str | None = None


class YesterdayTop(BaseModel):
    headline: str
    url: str


class Stage1Stats(BaseModel):
    candidates: int = 0
    dupe_groups: int = 0
    filtered_non_core_items: int = Field(default=0, ge=0)


class AiBriefContent(BaseModel):
    """完整简报文档。存 ai_daily_briefs.content。"""

    version: Literal[1, 2] = SCHEMA_VERSION
    brief_date: str  # YYYY-MM-DD
    subject: str = Field(max_length=44)          # 邮件主题：抓眼球中文标题
    preheader: str = Field(max_length=60)        # "另外：" + 第二新闻
    editorial: str = Field(default="", max_length=220)  # 编辑导语：2-3 句讲清当天头条
    intro_bullets: list[str] = Field(min_length=1, max_length=4)
    # 今日精选模块①今日AI ②AI大神：digest 驱动（从 Gmail digest 邮件生成）
    today_ai: DigestSection | None = None
    ai_masters: DigestSection | None = None
    # 工具学习板块 ③AI研究 ④AI工程 ⑤Agent工具：均 digest 驱动
    ai_research: DigestSection | None = None
    ai_engineering: DigestSection | None = None
    agent_tools: DigestSection | None = None
    # 旧 crawler 驱动板块（暂空）
    featured: list[FeaturedItem] = Field(default_factory=list, max_length=4)
    tools: list[Tool] = Field(default_factory=list, max_length=5)
    daily_tip: DailyTip | None = None
    quick_hits: list[QuickHit] = Field(default_factory=list, max_length=6)
    yesterday_top: YesterdayTop | None = None
    model: str | None = None
    stage1_stats: Stage1Stats | None = None

    @model_validator(mode="after")
    def remove_v2_engineering_content(self) -> AiBriefContent:
        if self.version == 2:
            self.ai_engineering = None
            self.featured = [
                item for item in self.featured if item.theme != Theme.AI_ENGINEERING
            ]
        return self
