"""Foundation 完整性 — 验证 Pydantic models 能完整往返写入读出 Postgres。"""
import os
from datetime import date, time
from uuid import uuid4

import pytest
import psycopg

from python.subscriber import Subscriber, SubscriberPreferences
from python.content import Source, ArticleRaw
from python.delivery import BriefCandidate, DailyBrief
from python.enums import (
    SubscriberStatus, Plan, SourceType, SourceCategory, Locale, Topic,
)


@pytest.fixture(scope="module")
def db():
    """连本地 docker-compose Postgres 副本。CI 用 service container。"""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://nev:nev_local_dev@localhost:54322/nev_brief",
    )
    conn = psycopg.connect(url)
    yield conn
    conn.close()


@pytest.mark.integration
def test_subscriber_roundtrip(db):
    s = Subscriber(
        email=f"test-{uuid4()}@example.com",
        status=SubscriberStatus.ACTIVE,
        plan=Plan.FREE,
        push_time=time(7, 30),
    )
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO subscribers (id, email, status, plan, push_time, unsubscribe_token)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (str(s.id), s.email, s.status.value, s.plan.value,
             s.push_time, str(s.unsubscribe_token)),
        )
        cur.execute("SELECT email, status FROM subscribers WHERE id = %s", (str(s.id),))
        row = cur.fetchone()
    db.commit()
    assert row[0] == s.email
    assert row[1] == "active"


@pytest.mark.integration
def test_subscriber_email_unique_constraint(db):
    email = f"dup-{uuid4()}@example.com"
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO subscribers (email, status, plan) VALUES (%s, 'active', 'free')",
            (email,),
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO subscribers (email, status, plan) VALUES (%s, 'active', 'free')",
                (email,),
            )
        db.rollback()


@pytest.mark.integration
def test_articles_raw_url_unique(db):
    src_id = uuid4()
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO sources (id, name, type, url, authority, locale, category)
               VALUES (%s, '36氪', 'rss', 'https://36kr.com/feed', 9, 'zh', 'media')""",
            (str(src_id),),
        )
        url = f"https://example.com/{uuid4()}"
        cur.execute(
            "INSERT INTO articles_raw (source_id, url) VALUES (%s, %s)",
            (str(src_id), url),
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO articles_raw (source_id, url) VALUES (%s, %s)",
                (str(src_id), url),
            )
        db.rollback()


@pytest.mark.integration
def test_brief_candidate_too_long_title_rejected_at_app_layer():
    """Pydantic 层就阻止超字数，DB 不需要 CHECK 约束。"""
    with pytest.raises(Exception):
        BriefCandidate(
            rank=1,
            cluster_id=uuid4(),
            title="x" * 26,
            summary="ok",
            brands=[],
            topics=[],
            source_links=[],
            global_importance=50,
        )
