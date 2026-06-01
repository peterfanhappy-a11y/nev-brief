from datetime import date
from unittest.mock import MagicMock

import pytest

from nev_composer.runner import run_for_date
from nev_composer.storage import ActiveSubscriber


@pytest.fixture
def patched_runner(monkeypatch):
    """Auto-mock storage + renderer functions; tests inject their behavior."""
    calls: dict = {"upserts": [], "commits": 0, "rollbacks": 0}

    monkeypatch.setattr("nev_composer.runner.fetch_latest_sales", lambda c, d: [])
    monkeypatch.setattr(
        "nev_composer.runner.render_html",
        lambda ctx: f"<html>{len(ctx['top_items'])}</html>",
    )
    monkeypatch.setattr(
        "nev_composer.runner.render_text",
        lambda ctx: f"text {len(ctx['top_items'])}",
    )

    def fake_upsert(conn, sub_id, brief_date, html, text, sel):
        calls["upserts"].append({"sub_id": sub_id, "html": html, "selected": sel})
    monkeypatch.setattr("nev_composer.runner.upsert_delivery", fake_upsert)

    conn = MagicMock()
    conn.commit.side_effect = lambda: calls.update(commits=calls["commits"] + 1)
    conn.rollback.side_effect = lambda: calls.update(rollbacks=calls["rollbacks"] + 1)
    return calls, conn


def _sub(sid="s1", email="a@x.com", brands=None, topics=None):
    return ActiveSubscriber(
        id=sid, email=email, push_time="08:00:00", unsubscribe_token=f"tok-{sid}",
        pref_brands=brands or [], pref_topics=topics or [],
    )


def _cand(cluster_id="cl1", topics=None, brands=None, global_imp=50.0):
    return {
        "cluster_id": cluster_id, "title": f"t-{cluster_id}",
        "summary": "s", "brands": brands or [], "topics": topics or [],
        "source_links": [], "global_importance": global_imp,
    }


def test_no_candidates_short_circuits(patched_runner, monkeypatch):
    calls, conn = patched_runner
    monkeypatch.setattr("nev_composer.runner.fetch_daily_brief_candidates", lambda c, d: None)
    monkeypatch.setattr("nev_composer.runner.fetch_active_subscribers", lambda c: [_sub()])
    result = run_for_date(conn, date(2026, 5, 31))
    assert result["composed"] == 0
    assert result.get("reason") == "no_candidates"
    assert calls["upserts"] == []


def test_no_active_subscribers(patched_runner, monkeypatch):
    calls, conn = patched_runner
    monkeypatch.setattr("nev_composer.runner.fetch_daily_brief_candidates",
                        lambda c, d: [_cand()])
    monkeypatch.setattr("nev_composer.runner.fetch_active_subscribers", lambda c: [])
    result = run_for_date(conn, date(2026, 5, 31))
    assert result["composed"] == 0


def test_composes_each_subscriber_separately(patched_runner, monkeypatch):
    calls, conn = patched_runner
    monkeypatch.setattr("nev_composer.runner.fetch_daily_brief_candidates",
                        lambda c, d: [_cand("cl1"), _cand("cl2")])
    monkeypatch.setattr("nev_composer.runner.fetch_active_subscribers",
                        lambda c: [_sub("s1", "a@x.com"), _sub("s2", "b@x.com")])
    result = run_for_date(conn, date(2026, 5, 31))
    assert result["composed"] == 2
    assert calls["commits"] == 2
    assert len(calls["upserts"]) == 2
    assert {u["sub_id"] for u in calls["upserts"]} == {"s1", "s2"}


def test_only_subscriber_email_filter(patched_runner, monkeypatch):
    calls, conn = patched_runner
    monkeypatch.setattr("nev_composer.runner.fetch_daily_brief_candidates",
                        lambda c, d: [_cand("cl1")])
    monkeypatch.setattr("nev_composer.runner.fetch_active_subscribers",
                        lambda c: [_sub("s1", "a@x.com"), _sub("s2", "b@x.com")])
    result = run_for_date(conn, date(2026, 5, 31), only_subscriber_email="A@x.com")
    assert result["subscribers"] == 1
    assert result["composed"] == 1
    assert calls["upserts"][0]["sub_id"] == "s1"


def test_failure_in_one_doesnt_block_others(patched_runner, monkeypatch):
    calls, conn = patched_runner
    monkeypatch.setattr("nev_composer.runner.fetch_daily_brief_candidates",
                        lambda c, d: [_cand("cl1")])
    monkeypatch.setattr("nev_composer.runner.fetch_active_subscribers",
                        lambda c: [_sub("s1"), _sub("s2")])

    def flaky_upsert(conn, sub_id, brief_date, html, text, sel):
        if sub_id == "s1":
            raise RuntimeError("simulated DB error")
        calls["upserts"].append({"sub_id": sub_id})
    monkeypatch.setattr("nev_composer.runner.upsert_delivery", flaky_upsert)
    result = run_for_date(conn, date(2026, 5, 31))
    assert result["composed"] == 1
    assert result["failed"] == 1
    assert calls["rollbacks"] == 1
    assert calls["commits"] == 1


def test_overseas_split(patched_runner, monkeypatch):
    """Items with 'overseas' topic should go to overseas_items in render context."""
    calls, conn = patched_runner
    monkeypatch.setattr("nev_composer.runner.fetch_daily_brief_candidates", lambda c, d: [
        _cand("cl-main", topics=["new_car"]),
        _cand("cl-over", topics=["overseas"]),
    ])
    monkeypatch.setattr("nev_composer.runner.fetch_active_subscribers", lambda c: [_sub()])

    captured = {}

    def capture_html(ctx):
        captured["ctx"] = ctx
        return "<html/>"
    monkeypatch.setattr("nev_composer.runner.render_html", capture_html)
    monkeypatch.setattr("nev_composer.runner.render_text", lambda ctx: "x")

    run_for_date(conn, date(2026, 5, 31))
    ctx = captured["ctx"]
    main_ids = [i["cluster_id"] for i in ctx["top_items"]]
    over_ids = [i["cluster_id"] for i in ctx["overseas_items"]]
    assert "cl-main" in main_ids
    assert "cl-over" in over_ids
    assert "cl-main" not in over_ids
    assert "cl-over" not in main_ids
