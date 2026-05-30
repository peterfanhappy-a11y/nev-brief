"""验收门 2: 5 同源转载 → 1 cluster_id
验收门 3: 10 事件聚类准确率 ≥ 80%

这些测试用 dict fallback，无需 DeepSeek。
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

from nev_pipeline.clustering import ClusterCandidate
from nev_pipeline.entity_dict import find_brands_in_text
from nev_pipeline.entity_extractor import Entities
from nev_pipeline.runner import process_article

FIXTURES = Path(__file__).parent / "fixtures"


async def _fake_extract(title: str, content: str) -> Entities:
    """Simulate DeepSeek failure → dict-fallback path (acceptance gate 4 path)."""
    text = f"{title} {content}"
    return Entities(brands=find_brands_in_text(text), used_fallback=True)


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


@pytest.mark.asyncio
async def test_5_same_source_articles_one_cluster(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec 验收门 2: 注入 5 篇同源转载 → 1 个 cluster_id"""
    monkeypatch.setattr("nev_pipeline.runner.extract_entities", _fake_extract)
    articles = json.loads(
        (FIXTURES / "same_source_5.json").read_text(encoding="utf-8")
    )
    assert len(articles) == 5

    recent: list[ClusterCandidate] = []
    cluster_ids: list[str] = []
    for i, a in enumerate(articles):
        raw = {
            "id": f"r{i}",
            "source_id": f"s{i}",
            "title": a["title"],
            "content": a["content"],
            "published_at": _parse_dt(a["published_at"]),
            "source_authority": a.get("source_authority", 7),
        }
        processed = await process_article(raw, recent)
        cluster_ids.append(processed["cluster_id"])
        recent.append(
            ClusterCandidate(
                brands=processed["brands"],
                models=processed["models"],
                simhash=processed["simhash"],
                published_at=raw["published_at"],
                cluster_id=processed["cluster_id"],
            )
        )

    unique_clusters = set(cluster_ids)
    assert len(unique_clusters) == 1, (
        f"want 1 cluster, got {len(unique_clusters)}: {cluster_ids}"
    )


@pytest.mark.asyncio
async def test_10_events_clustering_accuracy(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec 验收门 3: 10 事件聚类准确率 ≥ 80%"""
    monkeypatch.setattr("nev_pipeline.runner.extract_entities", _fake_extract)
    data = json.loads(
        (FIXTURES / "cluster_events.json").read_text(encoding="utf-8")
    )
    events = data["events"]
    assert len(events) == 10

    recent: list[ClusterCandidate] = []
    article_to_cluster: dict[str, str] = {}

    # Flatten + run distractors first to ensure events are still grouped
    # correctly despite noise interleaved into `recent`.
    distractors = data.get("distractors", [])
    for d_idx, a in enumerate(distractors):
        raw = {
            "id": f"d{d_idx}",
            "source_id": f"ds{d_idx}",
            "title": a["title"],
            "content": a["content"],
            "published_at": _parse_dt(a["published_at"]),
            "source_authority": 7,
        }
        processed = await process_article(raw, recent)
        recent.append(
            ClusterCandidate(
                brands=processed["brands"],
                models=processed["models"],
                simhash=processed["simhash"],
                published_at=raw["published_at"],
                cluster_id=processed["cluster_id"],
            )
        )

    # Process event articles in interleaved order to better mimic crawler flow
    flat: list[tuple[str, int, dict]] = []
    for ev in events:
        for idx, a in enumerate(ev["articles"]):
            flat.append((ev["event_id"], idx, a))

    for ev_id, idx, a in flat:
        raw = {
            "id": f"{ev_id}-{idx}",
            "source_id": f"s{idx}",
            "title": a["title"],
            "content": a["content"],
            "published_at": _parse_dt(a["published_at"]),
            "source_authority": 7,
        }
        processed = await process_article(raw, recent)
        article_to_cluster[f"{ev_id}-{idx}"] = processed["cluster_id"]
        recent.append(
            ClusterCandidate(
                brands=processed["brands"],
                models=processed["models"],
                simhash=processed["simhash"],
                published_at=raw["published_at"],
                cluster_id=processed["cluster_id"],
            )
        )

    correct_events = 0
    details: list[dict] = []
    for ev in events:
        cids = [
            article_to_cluster[f"{ev['event_id']}-{i}"]
            for i in range(len(ev["articles"]))
        ]
        counts = Counter(cids)
        _, majority_count = counts.most_common(1)[0]
        # require ≥ (N-1)/N — i.e. at most 1 article may end up in a different cluster
        if majority_count >= max(2, len(cids) - 1):
            correct_events += 1
        details.append(
            {
                "event": ev["event_id"],
                "label": ev["label"],
                "cluster_counts": dict(counts),
            }
        )

    accuracy = correct_events / len(events)
    assert accuracy >= 0.80, f"acc={accuracy:.0%}, want ≥80%. Details: {details}"
