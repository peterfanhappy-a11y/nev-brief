"""Build candidates jsonb entries for daily_briefs (spec §4.2)."""
from __future__ import annotations

from typing import Any

from nev_summarizer.cluster_aggregator import Cluster
from nev_summarizer.deepseek_summarizer import ClusterSummary


def build_candidate(
    cluster: Cluster,
    summary: ClusterSummary,
    global_importance: float,
    rank: int,
) -> dict[str, Any]:
    """Spec §4.2 candidates jsonb item.

    Source_links deduped on (source_id, url) preserving first occurrence.
    """
    seen: set[tuple[str, str]] = set()
    source_links: list[dict[str, str]] = []
    for a in cluster.articles:
        key = (a.source_id, a.url)
        if key in seen:
            continue
        seen.add(key)
        source_links.append({"name": a.source_name, "url": a.url})

    return {
        "rank": rank,
        "cluster_id": cluster.cluster_id,
        "title": summary.title,
        "summary": summary.summary,
        "brands": summary.brands,
        "topics": summary.topics,
        "source_links": source_links,
        "global_importance": round(global_importance, 2),
        "key_data": summary.key_data,
        "primary_source": summary.primary_source,
        "source_count": summary.source_count,
    }
