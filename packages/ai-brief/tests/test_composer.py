"""composer 渲染测试 — 8 板块 + 评分链接 + 无图色块兜底 + 条件板块。"""
from __future__ import annotations

from datetime import date

from ai_brief.composer import render
from ai_brief.schema import (
    AiBriefContent,
    DailyTip,
    FeaturedItem,
    QuickHit,
    Theme,
    Tool,
    YesterdayTop,
)


def _brief(**over) -> AiBriefContent:
    base = dict(
        brief_date="2026-07-02",
        subject="GPT-5 发布：一次对话写完整个 App",
        preheader="另外：Anthropic 拿下五角大楼合同",
        intro_bullets=["🧠 GPT-5 发布", "🛠 新工具上线"],
        featured=[
            FeaturedItem(
                theme=Theme.MODEL_RESEARCH, theme_label="模型研究", headline="GPT-5 发布",
                details=["超长上下文", "成本下降"], significance="改变行业格局。",
                url="https://openai.com/gpt5", source_name="OpenAI",
                og_image="https://img/gpt5.jpg",
            ),
            FeaturedItem(
                theme=Theme.ETHICS_REGULATION, theme_label="伦理监管", headline="欧盟 AI 法案生效",
                details=["分级监管"], significance="合规成本上升。",
                url="https://eu.example/ai-act", source_name="Reuters",
                og_image=None,  # 无图 → 色块兜底
            ),
        ],
        tools=[Tool(name="Cursor", one_liner="AI 代码编辑器", url="https://cursor.com")],
        daily_tip=DailyTip(title="写周报", body="用三段式 prompt。"),
        quick_hits=[QuickHit(text="某公司融资 1 亿", url="https://x/a")],
        yesterday_top=YesterdayTop(headline="昨日头条", url="https://y/top"),
    )
    base.update(over)
    return AiBriefContent(**base)


def test_render_html_all_sections() -> None:
    html, _ = render(
        _brief(), date(2026, 7, 2), delivery_id="d-123", unsubscribe_token="tok-9"
    )
    # 品牌 + 作者
    assert "AIVIZENS 趋势" in html
    assert "Fan" in html and "Fans" in html  # apostrophe 被 autoescape 成 &#39;
    assert "不凡的数智生活" in html
    # 主题板块
    assert "今日精选" in html
    assert "GPT-5 发布" in html
    assert "https://img/gpt5.jpg" in html  # 有图
    assert "欧盟 AI 法案生效" in html
    # 无图色块兜底：应出现 theme color 背景 + label
    assert "伦理监管" in html
    assert "#10B981" in html  # ethics_regulation 颜色
    # 速览
    assert "Cursor" in html
    assert "每日课堂" in html
    assert "某公司融资 1 亿" in html
    # 昨日最热
    assert "如果您错过了" in html
    assert "昨日头条" in html
    # 评分链接带 delivery_id（HTML 用 &amp; 保证有效性）
    assert "d=d-123&amp;s=3" in html
    assert "d=d-123&amp;s=1" in html
    # 退订 URL 是变量插值，& 被 autoescape 成 &amp;
    assert "tok-9&amp;product=ai" in html


def test_render_text_version() -> None:
    _, text = render(
        _brief(), date(2026, 7, 2), delivery_id="d-1", unsubscribe_token="t-1"
    )
    assert "AIVIZENS 趋势" in text
    assert "【模型研究】GPT-5 发布" in text
    assert "https://openai.com/gpt5" in text
    assert "s=3" in text
    assert "product=ai" in text


def test_render_omits_optional_sections() -> None:
    brief = _brief(tools=[], daily_tip=None, quick_hits=[], yesterday_top=None)
    html, _ = render(brief, date(2026, 7, 2), delivery_id="d", unsubscribe_token="t")
    assert "如果您错过了" not in html
    assert "每日课堂" not in html
    assert "热门 AI 工具" not in html
    # featured 仍在
    assert "今日精选" in html
