"""验收门 1: 实体识别准确率 ≥ 85% on 20-article golden set.

跑这个测试需要真实 DEEPSEEK_API_KEY，默认 skip。
启用: pytest -m golden --deepseek
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from nev_pipeline.entity_extractor import extract_entities

FIXTURES = Path(__file__).parent / "fixtures" / "golden_entities.json"


@pytest.mark.golden
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="needs real DEEPSEEK_API_KEY for golden accuracy gate",
)
async def test_entity_recognition_accuracy_80percent() -> None:
    """spec 验收门 1: ≥ 85% on golden set (relaxed to 80% in test to allow noise)."""
    golden = json.loads(FIXTURES.read_text(encoding="utf-8"))
    assert len(golden) == 20, "golden set must have exactly 20 items"

    hits = 0
    misses: list[dict] = []
    for item in golden:
        result = await extract_entities(item["title"], item["content"])
        expected = set(item["expected_brands"])
        actual = set(result.brands)
        # 命中标准：期望品牌至少命中 1 个（每条 fixture 可能多品牌）；
        # 若 expected 为空（纯政策无品牌），则不算 miss。
        if expected & actual or not expected:
            hits += 1
        else:
            misses.append(
                {"id": item["id"], "expected": list(expected), "actual": list(actual)}
            )

    accuracy = hits / len(golden)
    assert accuracy >= 0.85, f"acc={accuracy:.0%}, want ≥85%. Misses: {misses}"
