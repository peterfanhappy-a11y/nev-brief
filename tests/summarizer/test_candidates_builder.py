"""T6 tests — assemble candidates jsonb entry per spec §4.2."""
from __future__ import annotations

from datetime import datetime, timezone

from nev_summarizer.candidates_builder import build_candidate
from nev_summarizer.cluster_aggregator import Cluster, ClusterArticle
from nev_summarizer.deepseek_summarizer import ClusterSummary


def _cluster_with_sources(*pairs: tuple[str, str, str]) -> Cluster:
    now = datetime.now(timezone.utc)
    arts = [
        ClusterArticle(
            raw_id=f"r{i}", title="t", clean_text="c",
            url=url, source_id=sid, source_name=name,
            source_authority=8, published_at=now, importance_score=0.0,
        )
        for i, (sid, name, url) in enumerate(pairs)
    ]
    return Cluster(
        cluster_id="cl1", articles=arts, brands=[], models=[],
        topics=[], earliest_published=now,
    )


def _summary(**overrides: object) -> ClusterSummary:
    base: dict[str, object] = dict(
        title="t", summary="s", key_data={"type": "none", "values": {}},
        brands=["BYD"], topics=["new_car"],
        primary_source="36氪", source_count=2,
        used_truncation=False, retry_count=0,
    )
    base.update(overrides)
    return ClusterSummary(**base)  # type: ignore[arg-type]


def test_basic_shape() -> None:
    c = _cluster_with_sources(("s1", "36氪", "https://x/1"))
    cand = build_candidate(c, _summary(), global_importance=75.234, rank=1)
    assert cand["rank"] == 1
    assert cand["cluster_id"] == "cl1"
    assert cand["title"] == "t"
    assert cand["global_importance"] == 75.23
    assert cand["source_links"] == [{"name": "36氪", "url": "https://x/1"}]


def test_source_links_dedup() -> None:
    c = _cluster_with_sources(
        ("s1", "36氪", "https://x/1"),
        ("s1", "36氪", "https://x/1"),   # exact dup
        ("s2", "虎嗅", "https://x/2"),
    )
    cand = build_candidate(c, _summary(), global_importance=50.0, rank=2)
    assert len(cand["source_links"]) == 2
    assert {"name": "36氪", "url": "https://x/1"} in cand["source_links"]
    assert {"name": "虎嗅", "url": "https://x/2"} in cand["source_links"]


def test_passes_summary_metadata() -> None:
    c = _cluster_with_sources(("s1", "36氪", "https://x/1"))
    cand = build_candidate(
        c, _summary(brands=["Tesla", "NIO"]),
        global_importance=10.0, rank=3,
    )
    assert cand["brands"] == ["Tesla", "NIO"]
    assert cand["primary_source"] == "36氪"


def test_topics_from_cluster_not_summary() -> None:
    """topics 字段必须用 cluster.topics（enum 约束），忽略 summary.topics 自由词。"""
    now = datetime.now(timezone.utc)
    art = ClusterArticle(
        raw_id="r1", title="t", clean_text="c", url="u",
        source_id="s1", source_name="36氪", source_authority=8,
        published_at=now, importance_score=0.0,
    )
    cluster = Cluster(
        cluster_id="cl1", articles=[art], brands=[], models=[],
        topics=["new_car", "sales"],   # enum 值，来自 Agent-3 Prompt 1
        earliest_published=now,
    )
    cand = build_candidate(
        cluster,
        _summary(topics=["Robotaxi", "EPA 认证"]),   # 自由词，应被忽略
        global_importance=10.0, rank=1,
    )
    assert cand["topics"] == ["new_car", "sales"]
    assert "Robotaxi" not in cand["topics"]
