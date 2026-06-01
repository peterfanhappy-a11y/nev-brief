from datetime import date, timedelta

import pytest

from nev_composer.personalization import (
    UserPreferences, personal_score, select_top_n,
)


def _cand(cluster_id="cl1", brands=None, topics=None, global_imp=50.0):
    return {
        "cluster_id": cluster_id,
        "brands": brands or [],
        "topics": topics or [],
        "global_importance": global_imp,
    }


def test_formula_equal_weights():
    """Hand-calculate: global=100 brand=full topic=full fresh=1 -> 100."""
    today = date.today()
    user = UserPreferences(brands=["BYD"], topics=["new_car"])
    s = personal_score(
        _cand(brands=["BYD"], topics=["new_car"], global_imp=100.0),
        user, brief_date=today, today=today,
    )
    assert abs(s - 100.0) < 0.01


def test_freshness_today_vs_old():
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    c = _cand(global_imp=0.0)
    fresh = personal_score(c, user, brief_date=today, today=today)
    old = personal_score(c, user, brief_date=today - timedelta(days=1), today=today)
    assert fresh > old


def test_no_user_preferences_degrades_to_global():
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    s_high = personal_score(_cand(global_imp=100.0), user, today, today=today)
    s_low = personal_score(_cand(global_imp=10.0), user, today, today=today)
    assert s_high > s_low


def test_brand_match_adds_score():
    today = date.today()
    user = UserPreferences(brands=["BYD"], topics=[])
    s_hit = personal_score(_cand(brands=["BYD"], global_imp=50.0), user, today, today=today)
    s_miss = personal_score(_cand(brands=["Tesla"], global_imp=50.0), user, today, today=today)
    assert s_hit > s_miss


def test_topic_match_adds_score():
    today = date.today()
    user = UserPreferences(brands=[], topics=["new_car"])
    s_hit = personal_score(_cand(topics=["new_car"], global_imp=50.0), user, today, today=today)
    s_miss = personal_score(_cand(topics=["overseas"], global_imp=50.0), user, today, today=today)
    assert s_hit > s_miss


def test_select_top_n_basic():
    today = date.today()
    user = UserPreferences(brands=["BYD"], topics=[])
    candidates = [
        _cand(cluster_id=f"cl{i}", brands=["BYD"] if i % 2 == 0 else ["Tesla"], global_imp=float(i*10))
        for i in range(5)
    ]
    top = select_top_n(candidates, user, today, n=3, today=today)
    assert len(top) == 3
    # BYD candidates with high global should top the list
    assert top[0]["personal_score"] >= top[1]["personal_score"] >= top[2]["personal_score"]


def test_select_top_n_with_fewer_candidates():
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    top = select_top_n([_cand(global_imp=50.0)], user, today, n=10, today=today)
    assert len(top) == 1  # not forcing n=10


def test_select_top_n_stable_for_ties():
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    # All candidates same global -> all scores equal -> order preserved (Python stable sort)
    cands = [_cand(cluster_id=f"cl{i}", global_imp=50.0) for i in range(5)]
    top = select_top_n(cands, user, today, n=5, today=today)
    assert [c["cluster_id"] for c in top] == ["cl0", "cl1", "cl2", "cl3", "cl4"]


def test_select_top_n_annotates_personal_score():
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    top = select_top_n([_cand(global_imp=50.0)], user, today, today=today)
    assert "personal_score" in top[0]
