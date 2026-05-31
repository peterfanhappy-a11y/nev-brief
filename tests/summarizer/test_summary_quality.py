"""验收门 1+2 (relaxed): summary quality on 10 cluster golden set.

Gate 2 (hard): 100% of summaries within title ≤25 / summary ≤120 chars
Gate 1 (relaxed): brand recognition ≥80% (BGE semantic deferred to v2)

Requires real DEEPSEEK_API_KEY.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from nev_summarizer.cluster_aggregator import Cluster, ClusterArticle
from nev_summarizer.deepseek_summarizer import (
    SUMMARY_MAX,
    TITLE_MAX,
    summarize_cluster,
)

FIXTURES = Path(__file__).parent / "fixtures" / "golden_summaries.json"


def _make_cluster(item: dict) -> Cluster:
    now = datetime.now(UTC)
    arts = [
        ClusterArticle(
            raw_id=f"r-{i}",
            title=a["title"],
            clean_text=a["content"],
            url=f"https://test/{i}",
            source_id=f"s-{i}",
            source_name=a.get("source", "测试源"),
            source_authority=a.get("authority", 8),
            published_at=now,
            importance_score=50.0,
        )
        for i, a in enumerate(item["articles"])
    ]
    return Cluster(
        cluster_id=f"cl-{item['cluster_label']}",
        articles=arts,
        brands=item["expected_brands"],
        models=[],
        topics=[],
        earliest_published=now,
    )


@pytest.mark.golden
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="needs real DEEPSEEK_API_KEY",
)
async def test_summary_char_limits_100percent() -> None:
    """Gate 2: every generated summary must respect char limits.

    Algorithmic truncate guarantees this; this test verifies the guarantee holds.
    """
    golden = json.loads(FIXTURES.read_text(encoding="utf-8"))
    assert len(golden) == 10

    overruns: list[str] = []
    for item in golden:
        cluster = _make_cluster(item)
        summary = await summarize_cluster(cluster)
        if summary is None:
            overruns.append(f"{item['cluster_label']}: deepseek_failed")
            continue
        if len(summary.title) > TITLE_MAX:
            overruns.append(
                f"{item['cluster_label']}: title {len(summary.title)} chars"
            )
        if len(summary.summary) > SUMMARY_MAX:
            overruns.append(
                f"{item['cluster_label']}: summary {len(summary.summary)} chars"
            )

    assert not overruns, f"char-limit violations: {overruns}"


@pytest.mark.golden
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="needs real DEEPSEEK_API_KEY",
)
async def test_brand_recognition_80percent() -> None:
    """Gate 1 (relaxed): ≥80% of clusters should have at least one expected brand
    surface in summary.brands.
    """
    golden = json.loads(FIXTURES.read_text(encoding="utf-8"))
    hits = 0
    misses: list[str] = []
    for item in golden:
        cluster = _make_cluster(item)
        summary = await summarize_cluster(cluster)
        if summary is None:
            misses.append(f"{item['cluster_label']}: deepseek_failed")
            continue
        expected = set(item["expected_brands"])
        actual = set(summary.brands)
        if expected & actual or not expected:
            hits += 1
        else:
            misses.append(
                f"{item['cluster_label']}: expected {expected}, got {actual}"
            )
    accuracy = hits / len(golden)
    assert accuracy >= 0.80, f"acc={accuracy:.0%}, want ≥80%. Misses: {misses}"
