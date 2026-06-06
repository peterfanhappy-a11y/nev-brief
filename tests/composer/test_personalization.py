from datetime import date, timedelta

import pytest

from nev_composer.personalization import (
    UserPreferences, personal_score, select_diverse_top_n, select_top_n,
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


def test_diverse_select_caps_sales_to_one():
    """22 sales candidates → only 1 in Top 10, leaving room for other topics."""
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    cands = [_cand(cluster_id=f"sales{i}", topics=["sales"], global_imp=80.0 - i)
             for i in range(22)]
    cands += [_cand(cluster_id=f"tech{i}", topics=["tech"], global_imp=50.0 - i)
              for i in range(5)]
    cands += [_cand(cluster_id=f"new{i}", topics=["new_car"], global_imp=40.0 - i)
              for i in range(5)]
    top = select_diverse_top_n(cands, user, today, n=10, today=today)
    sales_count = sum(1 for c in top if "sales" in c["topics"])
    assert sales_count == 1, f"expected exactly 1 sales, got {sales_count}"


def test_diverse_select_prioritizes_sales_bucket_over_new_car():
    """Candidate with topics=[new_car, sales] goes to sales bucket (compressed)."""
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    cands = [
        _cand(cluster_id="hybrid", topics=["new_car", "sales"], global_imp=90.0),
        _cand(cluster_id="pure-new", topics=["new_car"], global_imp=80.0),
        _cand(cluster_id="another-sales", topics=["sales"], global_imp=70.0),
    ]
    top = select_diverse_top_n(cands, user, today, n=10, today=today)
    # Hybrid takes the single 'sales' slot; another-sales is excluded; pure-new admitted
    cluster_ids = [c["cluster_id"] for c in top]
    assert "hybrid" in cluster_ids
    assert "another-sales" not in cluster_ids
    assert "pure-new" in cluster_ids


def test_diverse_select_hard_cap_sales_even_when_thin():
    """sales is a hard cap — even when only sales exist, no backfill past quota.

    The brief honestly reflects "only 1 unique sales angle today" rather than
    smuggling compressed items back via backfill.
    """
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    cands = [_cand(cluster_id=f"s{i}", topics=["sales"], global_imp=90.0 - i)
             for i in range(15)]
    top = select_diverse_top_n(cands, user, today, n=10, today=today)
    assert len(top) == 1  # hard cap enforced; no padding
    assert top[0]["cluster_id"] == "s0"  # highest score wins the slot


def test_diverse_select_brand_cap_max_2_per_brand():
    """User feedback: 比亚迪 3 条太多. Brand appears at most 2 times in Top 10."""
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    # 5 BYD candidates spread across different topics — should select only 2
    cands = [
        _cand(cluster_id="byd1", brands=["BYD"], topics=["new_car"], global_imp=90),
        _cand(cluster_id="byd2", brands=["BYD"], topics=["battery_tech"], global_imp=85),
        _cand(cluster_id="byd3", brands=["BYD"], topics=["autonomous_driving"], global_imp=80),
        _cand(cluster_id="byd4", brands=["BYD"], topics=["overseas"], global_imp=75),
        _cand(cluster_id="byd5", brands=["BYD"], topics=["finance"], global_imp=70),
        _cand(cluster_id="nio1", brands=["NIO"], topics=["new_car"], global_imp=60),
        _cand(cluster_id="li1", brands=["Li Auto"], topics=["battery_tech"], global_imp=55),
    ]
    top = select_diverse_top_n(cands, user, today, n=10, today=today)
    byd_count = sum(1 for c in top if "BYD" in (c.get("brands") or []))
    assert byd_count == 2, f"expected BYD ≤ 2, got {byd_count}"


def test_diverse_select_brand_cap_multibrand_cluster_counts_all():
    """Cluster with brands=[BYD, NIO] counts toward BOTH brand quotas."""
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    cands = [
        _cand(cluster_id="byd_x_nio", brands=["BYD", "NIO"], topics=["new_car"], global_imp=90),
        _cand(cluster_id="byd2", brands=["BYD"], topics=["overseas"], global_imp=85),
        _cand(cluster_id="byd3", brands=["BYD"], topics=["finance"], global_imp=80),  # would be 3rd BYD
        _cand(cluster_id="nio2", brands=["NIO"], topics=["battery_tech"], global_imp=75),
        _cand(cluster_id="nio3", brands=["NIO"], topics=["autonomous_driving"], global_imp=70),  # would be 3rd NIO
    ]
    top = select_diverse_top_n(cands, user, today, n=10, today=today)
    cluster_ids = [c["cluster_id"] for c in top]
    assert "byd3" not in cluster_ids  # BYD already at 2 (multibrand + byd2)
    assert "nio3" not in cluster_ids  # NIO already at 2


def test_diverse_select_diverse_data_fills_to_n():
    """When data covers multiple topics, brief naturally fills to n=10."""
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    cands = []
    # 3 each of major topics
    for topic in ["sales", "new_car", "tech", "policy", "overseas", "supply_chain"]:
        for j in range(3):
            cands.append(_cand(cluster_id=f"{topic}{j}", topics=[topic],
                               global_imp=80.0 - j))
    top = select_diverse_top_n(cands, user, today, n=10, today=today)
    assert len(top) == 10
    # sales hard cap 1
    sales_count = sum(1 for c in top if "sales" in c["topics"])
    assert sales_count == 1


def test_diverse_select_all_hard_caps_enforced():
    """All topics are hard-cap — brief shrinks honestly rather than piling
    one topic to 10. 10 tech (quota 2) + 5 new_car (quota 3) = 5 items total."""
    today = date.today()
    user = UserPreferences(brands=[], topics=[])
    cands = [_cand(cluster_id=f"t{i}", topics=["tech"], global_imp=90.0 - i)
             for i in range(10)]
    cands += [_cand(cluster_id=f"n{i}", topics=["new_car"], global_imp=50.0 - i)
              for i in range(5)]
    top = select_diverse_top_n(cands, user, today, n=10, today=today)
    tech_count = sum(1 for c in top if "tech" in c["topics"])
    new_car_count = sum(1 for c in top if "new_car" in c["topics"])
    assert tech_count == 2  # tech quota lowered to discourage fallback bucket
    assert new_car_count == 3
    assert len(top) == 5  # 2 + 3, hard caps respected
