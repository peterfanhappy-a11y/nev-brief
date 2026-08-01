"""selector Stage-1 单测 — mock DeepSeek，验证序号→id 映射 / null / 去重过滤。"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from ai_brief import selector
from ai_brief.storage import Candidate


def _cands(n: int) -> list[Candidate]:
    return [
        Candidate(
            id=f"id-{i}", source_name=f"src{i}", locale="en", authority=10 - i,
            url=f"https://x/{i}", title=f"标题{i}", content=f"正文{i}", og_image=None,
        )
        for i in range(n)
    ]


DEEPSEEK_OUT = {
    "duplicate_groups": [[0, 3], [1]],  # 第二组 <2 应被过滤
    "themes": {
        "model_research": {"pick": 0, "backups": [3]},
        "product_tools": {"pick": 2, "backups": []},
        "skills_efficiency": {"pick": None, "backups": []},
        "ethics_regulation": {"pick": 4, "backups": [99]},  # 99 越界应被丢
    },
    "top2_overall": [0, 2],
    "tool_candidates": [2, 5],
    "quick_hits": [1, 4, 4],  # 重复应去重
    "daily_tip_topic": "用 Claude 写周报",
}


@pytest.mark.asyncio
async def test_select_maps_indices_to_ids() -> None:
    cands = _cands(6)
    with patch.object(
        selector, "extract_json_with_retry", new=AsyncMock(return_value=DEEPSEEK_OUT)
    ):
        res = await selector.select(cands)
    assert res is not None
    assert res.themes["model_research"]["pick"] == "id-0"
    assert res.themes["skills_efficiency"]["pick"] is None
    assert res.themes["ethics_regulation"]["backups"] == []  # 99 越界丢弃
    assert res.featured_ids() == ["id-0", "id-2", "id-4"]  # 固定主题顺序，跳过 null
    assert res.top2_overall == ["id-0", "id-2"]
    assert res.quick_hits == ["id-1", "id-4"]  # 去重
    assert res.dupe_group_count == 1  # 只有 [0,3] 保留
    assert res.daily_tip_topic == "用 Claude 写周报"


@pytest.mark.asyncio
async def test_select_none_on_api_fail() -> None:
    with patch.object(selector, "extract_json_with_retry", new=AsyncMock(return_value=None)):
        assert await selector.select(_cands(3)) is None


@pytest.mark.asyncio
async def test_select_empty_candidates() -> None:
    assert await selector.select([]) is None


@pytest.mark.asyncio
async def test_all_referenced_ids() -> None:
    cands = _cands(6)
    with patch.object(
        selector, "extract_json_with_retry", new=AsyncMock(return_value=DEEPSEEK_OUT)
    ):
        res = await selector.select(cands)
    assert res is not None
    refs = res.all_referenced_ids()
    assert "id-0" in refs and "id-2" in refs and "id-4" in refs and "id-5" in refs
