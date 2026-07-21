"""工具学习板块三解析器单测 —— 用真实 digest HTML fixture。纯函数，不触网。"""
from __future__ import annotations

from pathlib import Path

from ai_brief.digest.agent_parser import parse_agent_digest
from ai_brief.digest.engineering_parser import parse_engineering_digest
from ai_brief.digest.research_parser import parse_research_digest

FIX = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


# ── AI研究 ──────────────────────────────────────────────────────────────
def test_research_parses_two_papers() -> None:
    papers = parse_research_digest(_read("research_digest_2026-07-20.html"))
    assert len(papers) == 2
    tags = {p.source_tag for p in papers}
    assert tags == {"Arxiv", "HuggingFace"}
    for p in papers:
        assert len(p.takeaways) == 3
        assert p.url.startswith("http")
        assert p.title and "（" not in p.title  # 英文括注已去掉
        assert not p.takeaways[0].startswith(("1)", "1）"))  # 序号前缀已剥


def test_research_filename_matches_source() -> None:
    papers = parse_research_digest(_read("research_digest_2026-07-20.html"))
    by_tag = {p.source_tag: p for p in papers}
    assert by_tag["HuggingFace"].matches_filename("huggingface.png")
    assert not by_tag["HuggingFace"].matches_filename("arxiv.png")
    assert by_tag["Arxiv"].matches_filename("arxiv.png")


# ── AI工程 ──────────────────────────────────────────────────────────────
def test_engineering_parses_lecture() -> None:
    lec = parse_engineering_digest(_read("engineering_digest_2026-07-21.html"))
    assert lec is not None
    assert lec.lecture_no == 2
    assert lec.key_point  # 课程要点（主题）非空
    assert "工程底座" in lec.key_point
    assert len(lec.core_points) == 3
    for cp in lec.core_points:
        assert cp.subtitle and cp.body
        assert cp.body != cp.subtitle           # 正文已从小标题里剥出
        assert not cp.body.startswith(cp.subtitle)


# ── Agent工具 ───────────────────────────────────────────────────────────
def test_agent_parses_three_tools() -> None:
    tools = parse_agent_digest(_read("agent_digest_2026-07-21.html"))
    assert len(tools) == 3
    assert [t.rank for t in tools] == [1, 2, 3]
    assert [t.stars for t in tools] == ["10,983", "4,269", "2,854"]
    for t in tools:
        assert len(t.points) == 3
        assert t.url.startswith("https://github.com/")
        assert not t.name.lower().startswith("github/")  # Github/ 前缀已剥
