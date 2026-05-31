"""验收门 3: CAAM 销量抽取准确率。需要真 DEEPSEEK_API_KEY，默认 skip。

启用: pytest -m golden tests/summarizer/test_sales_accuracy.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from nev_summarizer.sales.caam_parser import extract_sales_from_article

FIXTURES = Path(__file__).parent / "fixtures" / "caam_monthly_5.json"


@pytest.mark.golden
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="needs real DEEPSEEK_API_KEY",
)
async def test_caam_sales_extraction_accuracy() -> None:
    """≥80% of expected (brand, units) pairs must be detected.

    Counts hits when:
    - expected brand_canonical appears in actual records
    - actual units within ±5% of expected
    """
    golden = json.loads(FIXTURES.read_text(encoding="utf-8"))
    assert len(golden) == 5

    total_expected = 0
    total_hits = 0
    misses: list[str] = []

    for item in golden:
        records = await extract_sales_from_article(item["content"])
        actual_by_brand = {r.brand_code: r for r in records}
        for expected in item["expected_records"]:
            total_expected += 1
            brand = expected["brand_canonical"]
            actual = actual_by_brand.get(brand)
            if actual is None:
                misses.append(f"{item['id']}: missing {brand}")
                continue
            exp_units = expected["units"]
            if abs(actual.units - exp_units) / max(exp_units, 1) > 0.05:
                misses.append(
                    f"{item['id']}: {brand} units {actual.units} vs expected {exp_units}"
                )
                continue
            total_hits += 1

    accuracy = total_hits / total_expected
    assert accuracy >= 0.80, (
        f"acc={accuracy:.0%} ({total_hits}/{total_expected}), want ≥80%. "
        f"Misses: {misses}"
    )
