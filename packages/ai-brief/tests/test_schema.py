"""AiBriefContent schema 回环 + 校验测试。"""
from __future__ import annotations

import pytest
from ai_brief.schema import (
    AiBriefContent,
    DailyTip,
    FeaturedItem,
    QuickHit,
    Theme,
    Tool,
    YesterdayTop,
)
from pydantic import ValidationError


def _minimal_featured() -> FeaturedItem:
    return FeaturedItem(
        theme=Theme.MODEL_RESEARCH,
        theme_label="模型研究",
        headline="OpenAI 发布 o5",
        details=["详情一", "详情二"],
        significance="这很重要因为它改变了推理成本结构。",
        url="https://openai.com/news/o5",
        source_name="OpenAI Blog",
        og_image="https://openai.com/img/o5.png",
        article_id="abc-123",
    )


def _engineering_featured() -> FeaturedItem:
    return _minimal_featured().model_copy(
        update={"theme": Theme.AI_ENGINEERING, "theme_label": "AI工程"},
    )


def test_minimal_valid_brief() -> None:
    brief = AiBriefContent(
        brief_date="2026-07-02",
        subject="OpenAI 发布 o5：一次对话写完整个 App",
        preheader="另外：Anthropic 拿下五角大楼合同",
        intro_bullets=["🧠 o5 发布"],
        featured=[_minimal_featured()],
    )
    assert brief.version == 1
    assert brief.featured[0].theme == Theme.MODEL_RESEARCH
    assert brief.tools == []
    assert brief.yesterday_top is None


def test_json_roundtrip() -> None:
    brief = AiBriefContent(
        brief_date="2026-07-02",
        subject="主题",
        preheader="另外：第二条",
        intro_bullets=["🧠 a", "🛠 b"],
        featured=[_minimal_featured()],
        tools=[Tool(name="Cursor", one_liner="AI 代码编辑器", url="https://cursor.com")],
        daily_tip=DailyTip(title="写周报", body="用三段式 prompt。"),
        quick_hits=[QuickHit(text="某公司融资 1 亿", url="https://x.com/a")],
        yesterday_top=YesterdayTop(headline="昨日头条", url="https://x.com/y"),
    )
    dumped = brief.model_dump_json()
    restored = AiBriefContent.model_validate_json(dumped)
    assert restored == brief


def test_featured_allows_empty() -> None:
    # digest 驱动版：模块1&2 走 today_ai/ai_masters，featured（模块3&4）可为空
    brief = AiBriefContent(
        brief_date="2026-07-02",
        subject="主题",
        preheader="另外：x",
        intro_bullets=["a"],
        featured=[],
    )
    assert brief.featured == []
    assert brief.today_ai is None and brief.ai_masters is None


def test_v2_purges_all_featured_content() -> None:
    brief = AiBriefContent(
        version=2,
        brief_date="2026-07-02",
        subject="主题",
        preheader="另外：x",
        intro_bullets=["a"],
        featured=[_minimal_featured(), _engineering_featured()],
    )

    assert brief.featured == []


def test_v1_keeps_featured_content() -> None:
    brief = AiBriefContent(
        version=1,
        brief_date="2026-07-02",
        subject="主题",
        preheader="另外：x",
        intro_bullets=["a"],
        featured=[_minimal_featured(), _engineering_featured()],
    )

    assert [item.theme for item in brief.featured] == [
        Theme.MODEL_RESEARCH,
        Theme.AI_ENGINEERING,
    ]


def test_featured_max_four() -> None:
    with pytest.raises(ValidationError):
        AiBriefContent(
            brief_date="2026-07-02",
            subject="主题",
            preheader="另外：x",
            intro_bullets=["a"],
            featured=[_minimal_featured()] * 5,
        )


def test_bad_theme_rejected() -> None:
    with pytest.raises(ValidationError):
        FeaturedItem(
            theme="nonsense",  # type: ignore[arg-type]
            theme_label="x",
            headline="h",
            details=["d"],
            significance="s",
            url="https://x.com",
            source_name="src",
        )
