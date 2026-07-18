"""summarizer Stage-2 单测 — mock DeepSeek，验证 ref→url 注入（防幻觉）+ 校验重试。"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from ai_brief import summarizer
from ai_brief.schema import YesterdayTop
from ai_brief.selector import SelectionResult
from ai_brief.storage import Candidate


def _cand(cid: str, title: str) -> Candidate:
    return Candidate(
        id=cid, source_name=f"src-{cid}", locale="en", authority=8,
        url=f"https://real.example/{cid}", title=title,
        content=f"{title} 的正文内容，足够长用于 stage-2 摘要生成测试。", og_image=f"https://img/{cid}.jpg",
    )


def _selection() -> SelectionResult:
    return SelectionResult(
        themes={
            "model_research": {"pick": "a", "backups": []},
            "product_tools": {"pick": "b", "backups": []},
            "skills_efficiency": {"pick": None, "backups": []},
            "ethics_regulation": {"pick": None, "backups": []},
        },
        top2_overall=["a", "b"],
        tool_candidates=["c"],
        quick_hits=["d"],
        daily_tip_topic="用 Claude 写周报",
        candidate_count=50,
        dupe_group_count=2,
    )


LLM_OUT = {
    "subject": "GPT-5 发布：一次对话写完整个 App",
    "preheader": "另外：Anthropic 拿下五角大楼合同",
    "intro_bullets": ["🧠 GPT-5 发布", "🛠 新工具上线"],
    "featured": [
        {"ref": 0, "theme": "model_research", "headline": "GPT-5 发布",
         "details": ["支持超长上下文", "推理成本下降"], "significance": "改变了行业格局。"},
        {"ref": 1, "theme": "product_tools", "headline": "新工具上线",
         "details": ["一键生成"], "significance": "降低了使用门槛。"},
    ],
    "tools": [{"ref": 2, "one_liner": "AI 代码助手"}],
    "daily_tip": {"title": "写周报技巧", "body": "用三段式 prompt。"},
    "quick_hits": [{"ref": 3, "text": "某公司融资 1 亿美元"},
                   {"ref": 99, "text": "越界 ref 应被丢弃"}],
}


@pytest.mark.asyncio
async def test_summarize_injects_db_urls() -> None:
    cands = [_cand("a", "GPT-5 发布"), _cand("b", "新工具"), _cand("c", "Cursor"), _cand("d", "融资新闻")]
    with patch.object(summarizer, "extract_json_with_retry", new=AsyncMock(return_value=LLM_OUT)):
        brief = await summarizer.summarize(
            _selection(), cands, brief_date="2026-07-02",
            yesterday_top=YesterdayTop(headline="昨日头条", url="https://y"),
        )
    assert brief is not None
    # url / og_image 来自 DB 而非 LLM（防幻觉核心）
    assert brief.featured[0].url == "https://real.example/a"
    assert brief.featured[0].og_image == "https://img/a.jpg"
    assert brief.featured[0].theme.value == "model_research"
    assert brief.featured[1].url == "https://real.example/b"
    assert len(brief.featured) == 2
    assert brief.tools[0].url == "https://real.example/c"
    assert brief.tools[0].name == "Cursor"
    # quick_hit ref=99 越界被丢，只留 1 条
    assert len(brief.quick_hits) == 1
    assert brief.quick_hits[0].url == "https://real.example/d"
    assert brief.yesterday_top.headline == "昨日头条"
    assert brief.subject.startswith("GPT-5")
    assert brief.stage1_stats.candidates == 50


@pytest.mark.asyncio
async def test_summarize_none_when_no_featured() -> None:
    sel = SelectionResult(
        themes={k: {"pick": None, "backups": []} for k in
                ["model_research", "product_tools", "skills_efficiency", "ethics_regulation"]},
        top2_overall=[], tool_candidates=[], quick_hits=[], daily_tip_topic="x",
    )
    with patch.object(summarizer, "extract_json_with_retry", new=AsyncMock(return_value=LLM_OUT)):
        assert await summarizer.summarize(sel, [], brief_date="2026-07-02", yesterday_top=None) is None


@pytest.mark.asyncio
async def test_summarize_none_on_api_fail() -> None:
    cands = [_cand("a", "x"), _cand("b", "y")]
    with patch.object(summarizer, "extract_json_with_retry", new=AsyncMock(return_value=None)):
        assert await summarizer.summarize(
            _selection(), cands, brief_date="2026-07-02", yesterday_top=None
        ) is None


@pytest.mark.asyncio
async def test_summarize_accepts_empty_featured() -> None:
    # digest 驱动版：featured（模块3&4）现允许为空，不再触发校验重试
    cands = [_cand("a", "x"), _cand("b", "y"), _cand("c", "z"), _cand("d", "w")]
    out = {**LLM_OUT, "featured": []}
    mock = AsyncMock(side_effect=[out])
    with patch.object(summarizer, "extract_json_with_retry", new=mock):
        brief = await summarizer.summarize(
            _selection(), cands, brief_date="2026-07-02", yesterday_top=None
        )
    assert brief is not None
    assert brief.featured == []
    assert mock.await_count == 1  # 不重试
