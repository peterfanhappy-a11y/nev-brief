"""T8 tests — runner pipeline orchestration with mocks."""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from nev_summarizer.cluster_aggregator import Cluster, ClusterArticle
from nev_summarizer.deepseek_summarizer import ClusterSummary
from nev_summarizer.runner import run_brief_for_date


def _cluster(cid: str, brand: str, when: datetime) -> Cluster:
    a = ClusterArticle(
        raw_id=f"r-{cid}", title="t", clean_text="c", url="u",
        source_id=f"s-{cid}", source_name="src", source_authority=8,
        published_at=when, importance_score=0.0,
    )
    return Cluster(
        cluster_id=cid, articles=[a],
        brands=[brand], models=[], topics=["new_car"],
        earliest_published=when,
    )


def _summary(
    title: str = "标题", summary: str = "摘要", truncated: bool = False,
) -> ClusterSummary:
    return ClusterSummary(
        title=title, summary=summary, key_data={}, brands=[], topics=[],
        primary_source="src", source_count=1,
        used_truncation=truncated, retry_count=0,
    )


@pytest.mark.asyncio
async def test_nev_filter_drops_non_nev_clusters(monkeypatch: pytest.MonkeyPatch) -> None:
    """非 NEV cluster (brand 不在 entity_dict canonical 集) 应该在 summarize 之前被丢弃。"""
    now = datetime.now(timezone.utc)
    # BYD is in entity_dict; "茅台" and brands=[] are not NEV
    nev_cluster = _cluster("nev1", "BYD", now)
    non_nev_brand = _cluster("noise1", "茅台", now)
    empty_brand = Cluster(
        cluster_id="empty1", articles=nev_cluster.articles,
        brands=[], models=[], topics=["finance"],
        earliest_published=now,
    )
    monkeypatch.setattr(
        "nev_summarizer.runner.aggregate_clusters",
        lambda conn, d: [nev_cluster, non_nev_brand, empty_brand],
    )

    summarized_ids: list[str] = []
    async def fake_sum(c: Cluster) -> ClusterSummary:
        summarized_ids.append(c.cluster_id)
        return _summary(title=f"t-{c.cluster_id}")
    monkeypatch.setattr("nev_summarizer.runner.summarize_cluster", fake_sum)
    monkeypatch.setattr("nev_summarizer.runner.upsert_daily_brief", lambda *a, **kw: None)

    result = await run_brief_for_date(MagicMock(), date(2026, 6, 2))
    # 只有 nev1 应该被 summarize 调用，noise1 和 empty1 被过滤掉
    assert summarized_ids == ["nev1"]
    # clusters 计数仍然是 3（信源进来 3 个）；summarized 是 1
    assert result["clusters"] == 3
    assert result["summarized"] == 1


@pytest.mark.asyncio
async def test_runs_full_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        "nev_summarizer.runner.aggregate_clusters",
        lambda conn, d: [_cluster("cl1", "BYD", now), _cluster("cl2", "Tesla", now)],
    )

    async def fake_sum(c: Cluster) -> ClusterSummary:
        return _summary(title=f"t-{c.cluster_id}")
    monkeypatch.setattr("nev_summarizer.runner.summarize_cluster", fake_sum)

    upserts: list[tuple[date, list]] = []
    monkeypatch.setattr(
        "nev_summarizer.runner.upsert_daily_brief",
        lambda conn, d, cands: upserts.append((d, cands)),
    )

    result = await run_brief_for_date(MagicMock(), date(2026, 5, 30))
    assert result["clusters"] == 2
    assert result["summarized"] == 2
    assert result["truncated"] == 0
    assert len(upserts) == 1
    _, cands = upserts[0]
    assert len(cands) == 2
    # ranked 1, 2
    assert {c["rank"] for c in cands} == {1, 2}


@pytest.mark.asyncio
async def test_failsafe_skips_none_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        "nev_summarizer.runner.aggregate_clusters",
        lambda conn, d: [_cluster("cl1", "BYD", now), _cluster("cl2", "Tesla", now)],
    )

    async def fake_sum(c: Cluster) -> ClusterSummary | None:
        if c.cluster_id == "cl1":
            return None  # DeepSeek failed for cl1
        return _summary(title="ok")
    monkeypatch.setattr("nev_summarizer.runner.summarize_cluster", fake_sum)

    upserts: list[tuple[date, list]] = []
    monkeypatch.setattr(
        "nev_summarizer.runner.upsert_daily_brief",
        lambda conn, d, cands: upserts.append((d, cands)),
    )

    result = await run_brief_for_date(MagicMock(), date(2026, 5, 30))
    assert result["summarized"] == 1  # cl1 skipped
    _, cands = upserts[0]
    assert len(cands) == 1


@pytest.mark.asyncio
async def test_truncation_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        "nev_summarizer.runner.aggregate_clusters",
        lambda conn, d: [_cluster("cl1", "BYD", now)],
    )

    async def fake_sum(c: Cluster) -> ClusterSummary:
        return _summary(truncated=True)
    monkeypatch.setattr("nev_summarizer.runner.summarize_cluster", fake_sum)

    monkeypatch.setattr("nev_summarizer.runner.upsert_daily_brief", lambda *a: None)
    result = await run_brief_for_date(MagicMock(), date(2026, 5, 30))
    assert result["truncated"] == 1


@pytest.mark.asyncio
async def test_empty_clusters_still_upserts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nev_summarizer.runner.aggregate_clusters", lambda *a: [])
    upserts: list[tuple[date, list]] = []
    monkeypatch.setattr(
        "nev_summarizer.runner.upsert_daily_brief",
        lambda conn, d, cands: upserts.append((d, cands)),
    )
    result = await run_brief_for_date(MagicMock(), date(2026, 5, 30))
    assert result["summarized"] == 0
    assert upserts == [(date(2026, 5, 30), [])]


@pytest.mark.asyncio
async def test_respects_top_n_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        "nev_summarizer.runner.aggregate_clusters",
        lambda conn, d: [_cluster(f"cl{i}", "BYD", now) for i in range(50)],
    )

    summarized_ids: list[str] = []

    async def fake_sum(c: Cluster) -> ClusterSummary:
        summarized_ids.append(c.cluster_id)
        return _summary(title=c.cluster_id)
    monkeypatch.setattr("nev_summarizer.runner.summarize_cluster", fake_sum)
    monkeypatch.setattr("nev_summarizer.runner.upsert_daily_brief", lambda *a: None)

    await run_brief_for_date(MagicMock(), date(2026, 5, 30), top_n=10)
    assert len(summarized_ids) == 10
