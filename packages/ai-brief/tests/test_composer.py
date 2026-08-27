"""composer 渲染测试 — digest 驱动版（今日AI / AI大神 section）+ 评分 + 条件板块。"""
from __future__ import annotations

from datetime import date
import re
from typing import Any

from ai_brief.composer import render
from ai_brief.schema import (
    AiBriefContent,
    DailyTip,
    DigestSection,
    DigestStory,
    Theme,
    Tool,
    YesterdayTop,
)


def _today_ai() -> DigestSection:
    return DigestSection(
        theme=Theme.MODEL_RESEARCH,
        header_image="https://img/today-ai.png",
        header_image_alt="Sonnet 5",
        stories=[
            DigestStory(
                headline="Anthropic 发布 Claude Sonnet 5",
                summary="Agent 编程能力媲美 Opus 4.8，价格仅三分之一。",
                url="https://www.anthropic.com/news/claude-sonnet-5",
                label="海外大模型 · 最有价值",
            ),
            DigestStory(
                headline="百度文心 5.0 登陆 WorldRouter",
                summary="2.4 万亿参数旗舰模型面向全球开发者开放。",
                url="https://www.qbitai.com/2026/07/442447.html",
                label="国内大模型 · 最有价值",
            ),
        ],
    )


def _ai_masters() -> DigestSection:
    return DigestSection(
        theme=Theme.PRODUCT_TOOLS,
        header_image="https://img/masters.png",
        stories=[
            DigestStory(
                headline="互联网广告商业模式已死",
                summary="机器人流量已超过人类，广告模式即将终结。",
                url="https://www.youtube.com/watch?v=UN47z_opfmo",
                label="Cloudflare CEO Matthew Prince",
            ),
        ],
    )


def _brief(**over: Any) -> AiBriefContent:
    base: dict[str, Any] = {
        "brief_date": "2026-07-06",
        "subject": "Claude Sonnet 5 发布：Agent 能力比肩旗舰",
        "preheader": "另外：阿里巴巴内部禁用 Claude Code",
        "editorial": "Anthropic 今日发布 Sonnet 5，以三分之一价格逼近 Opus 4.8。",
        "intro_bullets": ["🚀 Sonnet 5 发布", "🎤 大神论道"],
        "today_ai": _today_ai(),
        "ai_masters": _ai_masters(),
        "tools": [Tool(name="Cursor", one_liner="AI 代码编辑器", url="https://cursor.com")],
        "daily_tip": DailyTip(title="写周报", body="用三段式 prompt。"),
        "yesterday_top": YesterdayTop(headline="昨日头条", url="https://y/top"),
    }
    base.update(over)
    return AiBriefContent(**base)


def test_render_html_digest_sections() -> None:
    html, _ = render(
        _brief(),
        date(2026, 7, 6),
        delivery_id="d-123",
        unsubscribe_token="tok-9",  # noqa: S106 - inert test value
    )
    # 品牌 + 作者 + 问候 + 导语
    assert "Fan" in html and "Fans" in html
    assert "早上好" in html and "AI 洞察" in html
    # section header
    assert "今 日 精 选" in html
    # 今日AI section：label from config + 头图 + story
    assert "今日AI" in html
    assert "https://img/today-ai.png" in html
    assert "Anthropic 发布 Claude Sonnet 5" in html
    assert "海外大模型 · 最有价值" in html
    assert "百度文心 5.0 登陆 WorldRouter" in html
    # AI大神 section
    assert "AI大神" in html
    assert "https://img/masters.png" in html
    assert "Cloudflare CEO Matthew Prince" in html
    assert "阅读原文" in html
    # 昨日最热 + 评分
    assert "如果您错过了" in html
    assert "d=d-123&amp;s=3" in html
    assert "tok-9&amp;product=ai" in html


def test_render_text_digest_sections() -> None:
    _, text = render(
        _brief(),
        date(2026, 7, 6),
        delivery_id="d-1",
        unsubscribe_token="t-1",  # noqa: S106 - inert test value
    )
    assert "AIVIZENS 趋势" in text
    assert "《今日AI》" in text
    assert "Anthropic 发布 Claude Sonnet 5" in text
    assert "《AI大神》" in text
    assert "https://www.anthropic.com/news/claude-sonnet-5" in text
    assert "product=ai" in text


def test_render_omits_missing_ai_masters() -> None:
    brief = _brief(ai_masters=None)
    html, _ = render(
        brief,
        date(2026, 7, 6),
        delivery_id="d",
        unsubscribe_token="t",  # noqa: S106 - inert test value
    )
    assert "今日AI" in html
    assert "AI大神" not in html          # 缺失模块省略
    assert "https://img/masters.png" not in html


def test_render_engineering_labels_number_and_break_after_colon() -> None:
    brief = _brief(
        ai_engineering=DigestSection(
            theme=Theme.AI_ENGINEERING,
            subtitle="工程课程要点",
            cta_label="",
            stories=[
                DigestStory(
                    headline="问题：先让 AI 看懂项目",
                    summary="正文从下一行开始。",
                    url="",
                )
            ],
        )
    )

    html, text = render(
        brief,
        date(2026, 7, 6),
        delivery_id="d",
        unsubscribe_token="t",  # noqa: S106 - inert test value
    )

    assert "1. 问题：<br>先让 AI 看懂项目" in html
    assert re.search(r"1\. 问题：\s+先让 AI 看懂项目", text)


def test_greeting_name_from_email() -> None:
    from ai_brief.composer import greeting_name
    assert greeting_name("peter.fan.happy@gmail.com") == "Peter"
    assert greeting_name("Alice@x.com") == "Alice"
    assert greeting_name("123456@x.com") == ""
    assert greeting_name("a@x.com") == ""
