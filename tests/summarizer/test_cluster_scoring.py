"""Unit tests for nev_summarizer.cluster_scoring (T4, spec §6.4)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from nev_summarizer.cluster_aggregator import Cluster, ClusterArticle
from nev_summarizer.cluster_scoring import cluster_importance


def _make_cluster(*, source_ids, authorities, brands=None, topics=None,
                   earliest=None):
    now = datetime.now(timezone.utc)
    earliest = earliest or now
    articles = [
        ClusterArticle(
            raw_id=f"r{i}", title="t", clean_text="c",
            url=f"https://x/{i}",
            source_id=sid, source_name=f"s{i}", source_authority=auth,
            published_at=earliest, importance_score=0.0,
        )
        for i, (sid, auth) in enumerate(zip(source_ids, authorities, strict=False))
    ]
    return Cluster(
        cluster_id="cl1", articles=articles,
        brands=brands or [], models=[], topics=topics or [],
        earliest_published=earliest,
    )


def test_high_coverage_scores_higher():
    now = datetime.now(timezone.utc)
    single = _make_cluster(source_ids=["s1"], authorities=[8], earliest=now)
    multi  = _make_cluster(source_ids=["s1","s2","s3","s4","s5"],
                            authorities=[8]*5, earliest=now)
    assert cluster_importance(multi, now=now) > cluster_importance(single, now=now)


def test_high_authority_scores_higher():
    now = datetime.now(timezone.utc)
    low  = _make_cluster(source_ids=["s1"], authorities=[3], earliest=now)
    high = _make_cluster(source_ids=["s1"], authorities=[10], earliest=now)
    assert cluster_importance(high, now=now) > cluster_importance(low, now=now)


def test_hot_brand_adds_heat():
    now = datetime.now(timezone.utc)
    cold = _make_cluster(source_ids=["s1"], authorities=[5], brands=["JAC"], earliest=now)
    hot  = _make_cluster(source_ids=["s1"], authorities=[5], brands=["BYD"], earliest=now)
    assert cluster_importance(hot, now=now) > cluster_importance(cold, now=now)


def test_hot_topic_adds_heat():
    now = datetime.now(timezone.utc)
    cold = _make_cluster(source_ids=["s1"], authorities=[5], topics=["overseas"], earliest=now)
    hot  = _make_cluster(source_ids=["s1"], authorities=[5], topics=["new_car"], earliest=now)
    assert cluster_importance(hot, now=now) > cluster_importance(cold, now=now)


def test_freshness_decay():
    now = datetime.now(timezone.utc)
    fresh = _make_cluster(source_ids=["s1"], authorities=[5], earliest=now)
    stale = _make_cluster(source_ids=["s1"], authorities=[5],
                           earliest=now - timedelta(hours=20))
    assert cluster_importance(fresh, now=now) > cluster_importance(stale, now=now)


def test_score_range():
    now = datetime.now(timezone.utc)
    c = _make_cluster(source_ids=["s1","s2","s3","s4","s5"],
                       authorities=[10]*5, brands=["BYD"], topics=["new_car"], earliest=now)
    s = cluster_importance(c, now=now)
    assert 0 <= s <= 100
