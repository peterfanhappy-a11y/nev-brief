"""digest 解析器测试 —— 用真实 digest 邮件正文作 fixture。"""
from __future__ import annotations

from pathlib import Path

from ai_brief.digest.builder_parser import parse_builder_digest
from ai_brief.digest.events_parser import parse_events_digest

FIXTURES = Path(__file__).parent / "fixtures"


def _events_html() -> str:
    return (FIXTURES / "events_digest_2026-07-11.html").read_text(encoding="utf-8")


def _builder_text() -> str:
    return (FIXTURES / "builder_digest_2026-07-11.txt").read_text(encoding="utf-8")


# ── events (今日AI) ────────────────────────────────────────────────
def test_events_parses_three_items() -> None:
    items = parse_events_digest(_events_html())
    assert len(items) == 3
    assert [i.index for i in items] == [1, 2, 3]


def test_events_first_item_fields() -> None:
    a = parse_events_digest(_events_html())[0]
    assert "ChatGPT Work" in a.headline
    assert a.url.startswith("https://venturebeat.com/")
    assert a.category == "海外大模型公司"
    assert a.value_tag == "最有价值"
    assert "7月10日" in a.body and "ChatGPT Work" in a.body
    assert "阅读原文" not in a.body       # 不吞尾部链接文字
    assert "🖼️" not in a.body            # 头图说明不混入正文
    assert a.image_note                   # 有头图说明


def test_events_third_item_apple_openai() -> None:
    c = parse_events_digest(_events_html())[2]
    assert "苹果" in c.headline and "OpenAI" in c.headline
    assert c.url.startswith("https://techcrunch.com/")


def test_events_skips_editor_note_from_body() -> None:
    # 第2条带「📌 注：...」编辑备注，不应混进正文
    b = parse_events_digest(_events_html())[1]
    assert "📌" not in b.body
    assert "Muse Spark" in b.body


# ── builder (AI大神) ───────────────────────────────────────────────
def test_builder_parses_ten_items() -> None:
    items = parse_builder_digest(_builder_text())
    assert len(items) == 10
    assert [i.index for i in items] == list(range(1, 11))


def test_builder_top5_vs_fire5_and_images() -> None:
    items = parse_builder_digest(_builder_text())
    top5 = [i for i in items if i.is_top5]
    fire5 = [i for i in items if not i.is_top5]
    assert [i.index for i in top5] == [1, 2, 3, 4, 5]
    assert [i.index for i in fire5] == [6, 7, 8, 9, 10]
    # 只有后5条有配图
    assert all(not i.has_image for i in top5)
    assert all(i.has_image for i in fire5)


def test_builder_body_and_url() -> None:
    # 当前上游格式：人名内嵌在长标题里、无 [人名] 括号 → person 由下游 LLM 提取，
    # 这里只校验 parser 稳的部分：index/headline/body/url。
    items = parse_builder_digest(_builder_text())
    first = items[0]
    assert "GitHub COO Kyle Daigle" in first.headline
    assert "1700 万" in first.body or "1700万" in first.body
    assert first.url.startswith("https://www.youtube.com/")
    assert "http" not in first.body      # URL 不残留在正文
    assert "Sam Altman" in items[2].headline
