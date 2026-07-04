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
    assert "Fan" in html and "Fans" in html  # apostrophe 被 autoescape 成 &#39;
    assert "早上好" in html and "AI 洞察" in html  # 问候语 + 导语引子
    # 窄横幅 section header（含空格分隔）
    assert "今 日 精 选" in html
    assert "工 具 学 习" in html
    # 主题板块
    assert "GPT-5 发布" in html
    assert "https://img/gpt5.jpg" in html  # 有图
    assert "欧盟 AI 法案生效" in html
    # 主题 label 用小字彩色文本（非宽横幅），颜色仍在
    assert "#10B981" in html  # ethics_regulation label 颜色
    # therundown 式标签
    assert "详情：" in html
    assert "为什么重要：" in html
    # 工具学习
    assert "工 具 学 习" in html
    assert "Cursor" in html
    assert "热门 AI 课堂" in html
    assert "某公司融资 1 亿" not in html  # AI其他/quick_hits 已从模板移除
    # 昨日最热
    assert "如果您错过了" in html
    assert "昨日头条" in html
    # 评分链接带 delivery_id（HTML 用 &amp; 保证有效性）
    assert "d=d-123&amp;s=3" in html
    assert "d=d-123&amp;s=1" in html
    # 退订 URL 是变量插值，& 被 autoescape 成 &amp;
    assert "tok-9&amp;product=ai" in html


def test_greeting_name_from_email() -> None:
    from ai_brief.composer import greeting_name
    assert greeting_name("peter.fan.happy@gmail.com") == "Peter"
    assert greeting_name("Alice@x.com") == "Alice"
    assert greeting_name("123456@x.com") == ""       # 无字母 → 空
    assert greeting_name("a@x.com") == ""             # 太短 → 空


def test_render_editorial_and_greeting_name() -> None:
    from ai_brief.schema import AiBriefContent
    b = _brief()
    b = AiBriefContent(**{**b.model_dump(), "editorial": "OpenAI 今日发布 o5，一次对话即可生成完整应用。"})
    html, _ = render(b, date(2026, 7, 2), delivery_id="d", unsubscribe_token="t",
                     email="peter.fan.happy@gmail.com")
    assert "早上好，Peter！" in html
    assert "OpenAI 今日发布 o5" in html


def test_render_text_version() -> None:
    _, text = render(
        _brief(), date(2026, 7, 2), delivery_id="d-1", unsubscribe_token="t-1"
    )
    assert "AIVIZENS 趋势" in text
    assert "【今日AI】GPT-5 发布" in text  # label 从 config 取（MODEL_RESEARCH → 今日AI）
    assert "https://openai.com/gpt5" in text
    assert "s=3" in text
    assert "product=ai" in text


def test_render_omits_optional_sections() -> None:
    brief = _brief(tools=[], daily_tip=None, quick_hits=[], yesterday_top=None)
    html, _ = render(brief, date(2026, 7, 2), delivery_id="d", unsubscribe_token="t")
    assert "如果您错过了" not in html
    assert "热门 AI 课堂" not in html
    assert "热门 AI 工具" not in html
    # featured 仍在
    assert "今日精选" in html
