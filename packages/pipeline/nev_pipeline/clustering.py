"""Rule-based event clustering (T9).

Match criteria (all three required to merge):
1. Shared >=1 brand or model (canonical names)
2. Published within 24h window
3. SimHash Hamming distance <= 9 (~85% similarity)

Used by runner (T12) per article. Deterministic, no external services.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from nev_pipeline.simhash import are_similar

_WINDOW = timedelta(hours=24)
_SIMHASH_THRESHOLD = 9


@dataclass(frozen=True)
class ClusterCandidate:
    """Minimal shape needed for clustering decision.

    Decoupled from DB schema (articles_processed) so clustering stays
    purely rule-based and easy to unit-test.
    """
    brands: list[str]
    models: list[str]
    simhash: int
    published_at: datetime
    cluster_id: str | None  # None for new articles


def _entity_overlap(a: ClusterCandidate, b: ClusterCandidate) -> bool:
    a_entities = set(a.brands) | set(a.models)
    b_entities = set(b.brands) | set(b.models)
    return bool(a_entities & b_entities)


def find_or_create_cluster(article: ClusterCandidate, recent: list[ClusterCandidate]) -> str:
    """Find existing cluster_id for article among recent; otherwise mint new uuid4."""
    for candidate in recent:
        if candidate.cluster_id is None:
            continue
        if not _entity_overlap(article, candidate):
            continue
        if abs((article.published_at - candidate.published_at).total_seconds()) > _WINDOW.total_seconds():
            continue
        if not are_similar(article.simhash, candidate.simhash, threshold=_SIMHASH_THRESHOLD):
            continue
        return candidate.cluster_id
    return str(uuid4())
