"""Spec section 6.4 importance scoring formula (single article, T10).

Cluster-level recomputed by summarizer (Agent-4); this is the per-article baseline.

score = 100 * (authority*0.3 + coverage*0.3 + freshness*0.2 + entity_heat*0.2)

- authority: caller-provided 0-10 (clamped); from source credibility table.
- coverage: single-article baseline 0.2 (summarizer adjusts when cluster grows).
- freshness: linear decay over 24h; 0 at/after 24h.
- entity_heat: +0.5 if hot brand mentioned, +0.5 if hot topic mentioned (cap 1.0).
"""
from __future__ import annotations

from datetime import datetime, timezone

from nev_pipeline.entity_dict import load_entity_dict

HOT_TOPICS = frozenset({"new_car", "sales", "policy"})
_COVERAGE_SINGLE_ARTICLE = 0.2  # single-article baseline; cluster-level set by summarizer


def importance_score(
    authority: int,
    brands: list[str],
    topics: list[str],
    published_at: datetime | None,
    now: datetime | None = None,
) -> float:
    now = now or datetime.now(tz=timezone.utc)
    d = load_entity_dict()

    auth = min(authority, 10) / 10
    coverage = _COVERAGE_SINGLE_ARTICLE
    # HTML scrape sources (汽车之家, 车质网) often lack published_at because the
    # list page only exposes "X 小时前" text. Fall back to "now" (treat as fresh).
    pub = published_at or now
    age_hours = max((now - pub).total_seconds() / 3600, 0.0)
    freshness = max(0.0, 1.0 - age_hours / 24.0)

    heat = 0.0
    if set(brands) & d.hot_brands:
        heat += 0.5
    if set(topics) & HOT_TOPICS:
        heat += 0.5

    return 100.0 * (auth * 0.3 + coverage * 0.3 + freshness * 0.2 + heat * 0.2)
