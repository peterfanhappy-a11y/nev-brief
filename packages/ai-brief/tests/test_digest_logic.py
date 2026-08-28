"""condenser / image_judge 的纯逻辑单测（不触 API）。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from ai_brief.digest import condenser, image_judge
from ai_brief.digest.condenser import _rebalance
from ai_brief.digest.generate import _filter_agent_tools
from ai_brief.digest.image_judge import _parse_index
from ai_brief.digest.models import AgentTool, BuilderItem, EventItem, ResearchPaper


def _items() -> dict[int, BuilderItem]:
    out = {}
    for i in range(1, 11):
        out[i] = BuilderItem(
            index=i, is_top5=(i <= 5), person=f"P{i}", headline=f"H{i}", body="b", url="u"
        )
    return out


def test_rebalance_enforces_2a_3b() -> None:
    by = _items()
    order = _rebalance([1, 2, 6, 7, 8], by)          # 正好 2A + 3B
    assert order == [1, 2, 6, 7, 8]


def test_rebalance_fixes_wrong_counts() -> None:
    by = _items()
    # 模型错选 4 条 A、1 条 B → 应收敛到 2A + 3B
    order = _rebalance([1, 2, 3, 4, 6], by)
    a = [i for i in order if i <= 5]
    b = [i for i in order if i > 5]
    assert len(a) == 2 and len(b) == 3
    assert a == [1, 2]                                 # 保留前2个 A
    assert 6 in b                                       # 保留模型选的 B，其余按序补


def test_rebalance_all_b_only_picked() -> None:
    by = _items()
    order = _rebalance([6, 7, 8, 9, 10], by)
    a = [i for i in order if i <= 5]
    b = [i for i in order if i > 5]
    assert len(a) == 2 and len(b) == 3
    assert a == [1, 2]                                  # 无 A 被选 → 按序补 1,2


def test_clip_sentence() -> None:
    from ai_brief.digest.condenser import _clip_sentence
    # 短文本原样返回
    assert _clip_sentence("完整核心观点。", 120) == "完整核心观点。"
    # 超限 → 收在窗口内最后一个句末标点，成完整句、不留半截
    long = "他认为AI降低门槛，人人可创造。但成本控制是真痛点，账单可能暴涨失控。"
    r = _clip_sentence(long, 18)
    assert r.endswith("。") and len(r) <= 18
    # 窗口内无句末标点 → 去尾部连接词标点并加省略号
    r2 = _clip_sentence("要点一，要点二，要点三，要点四，要点五，要点六", 8)
    assert r2.endswith("…") and "，" not in r2[-1]


def test_parse_index() -> None:
    assert _parse_index("2", 3) == 2
    assert _parse_index("图 1", 3) == 1
    assert _parse_index("我选 0 号", 3) == 0
    assert _parse_index("5", 3) == 0                    # 越界 → 回退 0
    assert _parse_index("没有数字", 3) == 0


async def test_today_ai_invalid_model_output_reports_incomplete_despite_source_fallback() -> None:
    items = [
        EventItem(
            index=index,
            category="AI",
            value_tag="important",
            headline=f"Headline {index}",
            url=f"https://openai.com/{index}",
            body=f"Source body {index}",
            image_note="",
        )
        for index in range(1, 4)
    ]
    with patch.object(condenser, "extract_json_with_retry", new=AsyncMock(return_value={})):
        result = await condenser.condense_today_ai(items)

    assert result is not None
    assert result.complete is False
    assert [story.summary for story in result.value.stories] == [
        "Source body 1",
        "Source body 2",
        "Source body 3",
    ]


async def test_research_request_failure_reports_incomplete_with_source_fallback() -> None:
    paper = ResearchPaper(
        source_tag="Arxiv",
        title="Research title",
        takeaways=["Takeaway one", "Takeaway two"],
        url="https://arxiv.org/abs/1234.5678",
    )
    with patch.object(condenser, "extract_json_with_retry", new=AsyncMock(return_value=None)):
        result = await condenser.condense_research(paper)

    assert result is not None
    assert result.complete is False
    assert result.value.summary == "Takeaway one Takeaway two"


async def test_agent_invalid_output_reports_incomplete_when_rank_fallback_builds_stories() -> None:
    tools = [
        AgentTool(
            rank=rank,
            name=f"tool-{rank}",
            stars="10",
            points=[f"point-{rank}"],
            url=f"https://github.com/example/tool-{rank}",
        )
        for rank in range(1, 4)
    ]
    with patch.object(
        condenser,
        "extract_json_with_retry",
        new=AsyncMock(return_value={"picks": []}),
    ):
        result = await condenser.select_agent_tools(tools)

    assert result is not None
    assert result.complete is False
    assert [story.headline for story in result.value] == ["tool-1", "tool-2", "tool-3"]


def test_filter_agent_tools_excludes_requested_repositories() -> None:
    tools = [
        AgentTool(rank=1, name="openai/codex", stars="", points=[], url="https://github.com/openai/codex"),
        AgentTool(rank=2, name="Anthropic/claude", stars="", points=[], url="https://github.com/anthropics/claude"),
        AgentTool(rank=3, name="Google/Gemini", stars="", points=[], url="https://github.com/google/gemini"),
        AgentTool(rank=4, name="acme/agent-kit", stars="", points=[], url="https://github.com/acme/agent-kit"),
    ]

    filtered = _filter_agent_tools(tools)

    assert [tool.name for tool in filtered] == ["acme/agent-kit"]


def test_agent_prompt_does_not_suggest_an_unavailable_rank() -> None:
    assert '"rank": 4' not in condenser._AGENT_SYSTEM
    assert "rank 必须来自给定工具" in condenser._AGENT_SYSTEM


async def test_agent_selection_returns_three_tools() -> None:
    tools = [
        AgentTool(
            rank=rank,
            name=f"tool-{rank}",
            stars="10",
            points=[f"point-{rank}"],
            url=f"https://github.com/example/tool-{rank}",
        )
        for rank in range(1, 4)
    ]
    with patch.object(
        condenser,
        "extract_json_with_retry",
        new=AsyncMock(
            return_value={
                "picks": [
                    {"rank": 1, "summary": "one."},
                    {"rank": 2, "summary": "two."},
                    {"rank": 3, "summary": "three."},
                ]
            }
        ),
    ):
        result = await condenser.select_agent_tools(tools)

    assert result is not None
    assert len(result.value) == 3
    assert result.complete is True


async def test_agent_selection_ignores_duplicate_model_ranks_when_three_unique_are_complete(
) -> None:
    tools = [
        AgentTool(
            rank=rank,
            name=f"tool-{rank}",
            stars="10",
            points=[f"point-{rank}"],
            url=f"https://github.com/example/tool-{rank}",
        )
        for rank in range(1, 4)
    ]
    with patch.object(
        condenser,
        "extract_json_with_retry",
        new=AsyncMock(
            return_value={
                "picks": [
                    {"rank": 1, "summary": "one."},
                    {"rank": 2, "summary": "two."},
                    {"rank": 2, "summary": "duplicate."},
                    {"rank": 3, "summary": "three."},
                ]
            }
        ),
    ):
        result = await condenser.select_agent_tools(tools)

    assert result is not None
    assert len(result.value) == 3
    assert result.complete is True


def test_qwen_missing_credentials_reports_incomplete_fallback_to_first() -> None:
    with patch.object(image_judge.config, "qwen_api_key", return_value=None):  # type: ignore[attr-defined]
        result = image_judge.pick_image(
            [(b"first", "image/png"), (b"second", "image/png")],
            ["first", "second"],
            mode="today_ai",
        )

    assert result.index == 0
    assert result.complete is False


def test_qwen_request_failure_reports_incomplete_fallback_to_first() -> None:
    with patch.object(image_judge.httpx, "post", side_effect=RuntimeError("request failed")):  # type: ignore[attr-defined]
        result = image_judge.pick_image(
            [(b"first", "image/png"), (b"second", "image/png")],
            ["first", "second"],
            mode="today_ai",
            api_key="fixture-key",
        )

    assert result.index == 0
    assert result.complete is False


def test_qwen_invalid_output_reports_incomplete_even_when_first_image_is_uploaded() -> None:
    response = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": "no selection", "reasoning_content": ""}}]
    }
    with patch.object(image_judge.httpx, "post", return_value=response):  # type: ignore[attr-defined]
        result = image_judge.pick_image(
            [(b"first", "image/png"), (b"second", "image/png")],
            ["first", "second"],
            mode="today_ai",
            api_key="fixture-key",
        )

    assert result.index == 0
    assert result.complete is False
