"""digest 解析器测试 —— 用真实 digest 邮件正文作 fixture。"""
from __future__ import annotations

from pathlib import Path

from ai_brief.digest.builder_parser import parse_builder_digest
from ai_brief.digest.events_parser import parse_events_digest
from ai_brief.digest.research_parser import parse_research_digest

FIXTURES = Path(__file__).parent / "fixtures"


def _events_html() -> str:
    # 2026-07-21 起上游改版为 <div class="item">（label/title/summary/meta），一次给 8 条
    return (FIXTURES / "events_digest_2026-07-21.html").read_text(encoding="utf-8")


def _builder_text() -> str:
    return (FIXTURES / "builder_digest_2026-07-11.txt").read_text(encoding="utf-8")


def _current_events_html() -> str:
    return (FIXTURES / "events_digest_2026-08-16.html").read_text(encoding="utf-8")


def _h3_events_html() -> str:
    return (FIXTURES / "events_digest_h3_markup.html").read_text(encoding="utf-8")


def _current_research_html() -> str:
    return (FIXTURES / "research_digest_2026-08-16.html").read_text(encoding="utf-8")


# ── events (今日AI) ────────────────────────────────────────────────
def test_events_parses_all_items() -> None:
    items = parse_events_digest(_events_html())
    assert len(items) == 8
    assert [i.index for i in items] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_events_first_item_fields() -> None:
    a = parse_events_digest(_events_html())[0]
    assert "Writer" in a.headline and "Harness" in a.headline
    assert a.url.startswith("https://venturebeat.com/")
    assert a.category == "海外大模型公司"
    assert a.value_tag == "最有价值"
    assert a.image_note == "VentureBeat"          # 来源名留在 image_note
    assert not a.headline.startswith("1")          # 序号前缀已剥离
    assert "阅读原文" not in a.body                # 不吞链接文字
    assert "来源" not in a.body                    # meta 不混进正文


def test_events_label_split_and_body() -> None:
    c = parse_events_digest(_events_html())[2]
    assert c.category == "海外" and c.value_tag == "最吸引眼球"
    assert "清理陷阱" in c.headline
    assert "RAG" in c.body                          # 正文完整


def test_events_parses_current_email_markup() -> None:
    items = parse_events_digest(_current_events_html())
    assert len(items) == 3
    assert items[0].category == "海外大模型公司"
    assert items[0].value_tag == "最有价值"
    assert items[0].image_note == "TechCrunch"
    assert items[0].headline == "A new open model changes the serving race"
    assert "benchmark" in items[0].body
    assert items[0].url == "https://example.com/events/open-model"
    assert [item.index for item in items] == [1, 2, 3]


def test_events_parses_h3_email_markup() -> None:
    items = parse_events_digest(_h3_events_html())

    assert [item.index for item in items] == [1, 2, 3]
    assert items[0].headline == "Claude Cowork 内置浏览器上线"
    assert items[0].url == "https://example.com/events/cowork"
    assert items[0].category == "海外大模型公司"
    assert items[0].image_note == "Example News"
    assert "自主浏览网页" in items[0].body
    assert items[2].value_tag == "最吸引眼球"


def test_events_parses_flat_h2_email_markup_with_url_link_text() -> None:
    html = """
    <main>
      <h2>海外大模型公司 · 最有价值</h2>
      <div>
      <div>
        <h2>Anthropic lets Claude train Claude</h2>
        <p>模型团队用 <a href="https://example.com/background">背景材料</a>
        说明新的训练流程降低研究成本。</p>
        <p>TechCrunch · https://example.com/events/claude-trains-claude</p>
      </div>
      <h2>Nvidia expands its AI advantage beyond GPUs</h2>
      <p>面向更广泛用户的新工具上线。</p>
      <p>QbitAI · https://example.com/events/nvidia</p>
      </div>
      <h2>延伸阅读</h2>
      <p>这不是今日 AI 新闻。</p>
      <p>Example News · https://example.com/events/related</p>
      <h2>说明 · 附注</h2>
      <div>
        <h2>这不是事件一</h2>
        <p>Example News · https://example.com/events/not-an-event-one</p>
        <h2>这不是事件二</h2>
        <p>Example News · https://example.com/events/not-an-event-two</p>
      </div>
    </main>
    """

    items = parse_events_digest(html)

    assert [item.index for item in items] == [1, 2]
    assert items[0].category == "海外大模型公司"
    assert items[0].value_tag == "最有价值"
    assert items[0].image_note == "TechCrunch"
    assert items[0].url == "https://example.com/events/claude-trains-claude"
    assert "训练流程" in items[0].body
    assert items[1].category == "海外大模型公司"
    assert items[1].value_tag == "最有价值"
    assert items[1].url == "https://example.com/events/nvidia"


def test_research_parses_current_email_markup() -> None:
    papers = parse_research_digest(_current_research_html())
    assert len(papers) == 2
    assert papers[0].source_tag == "Arxiv"
    assert papers[0].title == "Evaluating long-horizon research agents"
    assert len(papers[0].takeaways) == 2
    assert papers[0].url == "https://arxiv.org/abs/2608.00001"
    assert papers[1].source_tag == "HuggingFace"
    assert papers[1].url == "https://huggingface.co/papers/2608.00002"


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
