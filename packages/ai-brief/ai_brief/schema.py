"""AiBriefContent — 每日简报文档的 pydantic schema（单一来源）。

Stage-2 DeepSeek 输出经此校验后存入 ai_daily_briefs.content jsonb。
校验点：字数上限、必填板块、theme 枚举、URL 白名单（在 summarizer 里代码层强制，
schema 只保证结构）。所有 max_length 是软约束——超限时 summarizer 触发重试/截断。
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class Theme(str, Enum):
    MODEL_RESEARCH = "model_research"
    PRODUCT_TOOLS = "product_tools"
    SKILLS_EFFICIENCY = "skills_efficiency"
    ETHICS_REGULATION = "ethics_regulation"


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


class AiBriefContent(BaseModel):
    """完整简报文档。存 ai_daily_briefs.content。"""

    version: int = SCHEMA_VERSION
    brief_date: str  # YYYY-MM-DD
    subject: str = Field(max_length=44)          # 邮件主题：抓眼球中文标题
    preheader: str = Field(max_length=60)        # "另外：" + 第二新闻
    editorial: str = Field(default="", max_length=220)  # 编辑导语：2-3 句讲清当天头条
    intro_bullets: list[str] = Field(min_length=1, max_length=4)
    featured: list[FeaturedItem] = Field(min_length=1, max_length=4)
    tools: list[Tool] = Field(default_factory=list, max_length=5)
    daily_tip: DailyTip | None = None
    quick_hits: list[QuickHit] = Field(default_factory=list, max_length=6)
    yesterday_top: YesterdayTop | None = None
    model: str | None = None
    stage1_stats: Stage1Stats | None = None
