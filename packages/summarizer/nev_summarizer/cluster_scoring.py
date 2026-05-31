"""Cluster-level importance scoring (spec §6.4).

Same shape as nev_pipeline.scoring.importance_score, but with proper
coverage = min(distinct_sources / 5, 1.0) — Agent-3 used a fixed 0.2 because a
single article has no multi-source signal; the summarizer recomputes once the
cluster has formed.
"""
from __future__ import annotations

from datetime import datetime, timezone

from nev_pipeline.entity_dict import load_entity_dict
from nev_pipeline.scoring import HOT_TOPICS

from nev_summarizer.cluster_aggregator import Cluster


def cluster_importance(cluster: Cluster, now: datetime | None = None) -> float:
    """Per spec §6.4 cluster-level score (0-100).

    score = 100 * (authority*0.3 + coverage*0.3 + freshness*0.2 + entity_heat*0.2)
    """
    now = now or datetime.now(tz=timezone.utc)
    d = load_entity_dict()

    auth = max((a.source_authority for a in cluster.articles), default=0) / 10
    unique_sources = {a.source_id for a in cluster.articles}
    coverage = min(len(unique_sources) / 5, 1.0)
    age_hours = max((now - cluster.earliest_published).total_seconds() / 3600, 0.0)
    freshness = max(0.0, 1.0 - age_hours / 24.0)
    # Graduated NEV relevance heat:
    # - 0.0  no entity_dict brand match → non-NEV noise (e.g. 微博/腾讯/AI)
    # - 0.4  cold NEV brand (in dict but not hot)
    # - 0.8  hot NEV brand
    # +0.2 bonus if topic is hot (new_car / sales / policy)
    # Capped at 1.0.
    cluster_brands = set(cluster.brands)
    nev_brands = cluster_brands & set(d.brands_by_canonical.keys())
    heat = 0.0
    if nev_brands:
        heat += 0.4
        if nev_brands & d.hot_brands:
            heat += 0.4
    if set(cluster.topics) & HOT_TOPICS:
        heat += 0.2
    heat = min(heat, 1.0)

    return 100.0 * (auth * 0.3 + coverage * 0.3 + freshness * 0.2 + heat * 0.2)
