"""Tests for nev_pipeline.scoring (T10)."""
from datetime import datetime, timedelta, timezone
from nev_pipeline.scoring import importance_score, HOT_TOPICS


def test_score_in_range():
    now = datetime.now(timezone.utc)
    s = importance_score(authority=8, brands=["BYD"], topics=["new_car"], published_at=now, now=now)
    assert 0 <= s <= 100


def test_high_authority_scores_higher():
    now = datetime.now(timezone.utc)
    s_low = importance_score(authority=3, brands=[], topics=[], published_at=now, now=now)
    s_high = importance_score(authority=10, brands=[], topics=[], published_at=now, now=now)
    assert s_high > s_low


def test_fresh_scores_higher_than_old():
    now = datetime.now(timezone.utc)
    s_fresh = importance_score(authority=5, brands=[], topics=[], published_at=now, now=now)
    s_old = importance_score(authority=5, brands=[], topics=[], published_at=now - timedelta(hours=20), now=now)
    assert s_fresh > s_old


def test_24h_old_freshness_zero():
    """At exactly 24h freshness == 0; beyond it stays 0 (clamp)."""
    now = datetime.now(timezone.utc)
    s_at_24h = importance_score(authority=5, brands=[], topics=[], published_at=now - timedelta(hours=24), now=now)
    s_beyond = importance_score(authority=5, brands=[], topics=[], published_at=now - timedelta(days=3), now=now)
    assert s_at_24h == s_beyond  # both have freshness == 0


def test_hot_brand_adds_heat():
    now = datetime.now(timezone.utc)
    # JAC is canonical (T2 entity_dict); not in hot list → cold baseline.
    s_cold = importance_score(authority=5, brands=["JAC"], topics=[], published_at=now, now=now)
    s_hot = importance_score(authority=5, brands=["BYD"], topics=[], published_at=now, now=now)
    assert s_hot > s_cold


def test_hot_topic_adds_heat():
    now = datetime.now(timezone.utc)
    s_meh = importance_score(authority=5, brands=[], topics=["overseas"], published_at=now, now=now)
    s_hot_topic = importance_score(authority=5, brands=[], topics=["new_car"], published_at=now, now=now)
    assert s_hot_topic > s_meh


def test_HOT_TOPICS_constant():
    assert "new_car" in HOT_TOPICS
    assert "sales" in HOT_TOPICS
    assert "policy" in HOT_TOPICS
