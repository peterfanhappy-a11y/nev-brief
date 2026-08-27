"""Real PostgreSQL coverage for the durable subscription rate-limit RPC."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://nev:nev_local_dev@localhost:54322/nev_brief",
)


def _hash(label: str) -> str:
    return hashlib.sha256(f"{label}-{uuid4()}".encode()).hexdigest()


def _attempt(
    conn: psycopg.Connection,
    ip_hash: str,
    email_hash: str,
    now_at: datetime,
) -> tuple[bool, int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT allowed, retry_after_seconds "
            "FROM check_ai_subscription_rate_limit(%s, %s, %s)",
            (ip_hash, email_hash, now_at),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return bool(row[0]), int(row[1])


@pytest.fixture
def db() -> psycopg.Connection:
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn


@pytest.mark.integration
def test_rate_limit_rpc_is_hardened_and_service_role_only(db: psycopg.Connection) -> None:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT procedure.prosecdef,
                   procedure.proconfig,
                   has_function_privilege(
                       'service_role', procedure.oid, 'EXECUTE'
                   ),
                   has_function_privilege('anon', procedure.oid, 'EXECUTE'),
                   has_function_privilege(
                       'authenticated', procedure.oid, 'EXECUTE'
                   )
            FROM pg_proc AS procedure
            JOIN pg_namespace AS namespace
              ON namespace.oid = procedure.pronamespace
            WHERE namespace.nspname = 'public'
              AND procedure.proname = 'check_ai_subscription_rate_limit'
            """
        )
        row = cur.fetchone()

    assert row == (True, ['search_path=""'], True, False, False)


@pytest.mark.integration
def test_ip_limit_blocks_attempt_six_until_fifteen_minute_window_ends(
    db: psycopg.Connection,
) -> None:
    now_at = datetime(2026, 8, 3, 1, 0, tzinfo=UTC)
    ip_hash = _hash("ip-threshold")

    results = [
        _attempt(db, ip_hash, _hash(f"email-{attempt}"), now_at)
        for attempt in range(1, 7)
    ]

    assert results == [(True, 0)] * 5 + [(False, 900)]
    assert _attempt(db, ip_hash, _hash("email-rollover"), now_at + timedelta(minutes=15)) == (
        True,
        0,
    )


@pytest.mark.integration
def test_email_limit_blocks_attempt_four_until_one_hour_window_ends(
    db: psycopg.Connection,
) -> None:
    now_at = datetime(2026, 8, 3, 1, 0, tzinfo=UTC)
    email_hash = _hash("email-threshold")

    results = [
        _attempt(db, _hash(f"ip-{attempt}"), email_hash, now_at)
        for attempt in range(1, 5)
    ]

    assert results == [(True, 0)] * 3 + [(False, 3600)]
    assert _attempt(db, _hash("ip-rollover"), email_hash, now_at + timedelta(hours=1)) == (
        True,
        0,
    )


@pytest.mark.integration
def test_concurrent_ip_attempts_are_serialized_without_lost_increments(
    db: psycopg.Connection,
) -> None:
    now_at = datetime(2026, 8, 3, 1, 0, tzinfo=UTC)
    ip_hash = _hash("concurrent-ip")
    workers = 12
    barrier = Barrier(workers)

    def concurrent_attempt(attempt: int) -> tuple[bool, int]:
        with psycopg.connect(DATABASE_URL) as conn:
            barrier.wait()
            return _attempt(conn, ip_hash, _hash(f"concurrent-email-{attempt}"), now_at)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(concurrent_attempt, range(workers)))

    assert sum(allowed for allowed, _retry_after in results) == 5
    assert sum(not allowed for allowed, _retry_after in results) == 7
    assert {retry_after for allowed, retry_after in results if not allowed} == {900}

    with db.cursor() as cur:
        cur.execute(
            "SELECT attempt_count FROM ai_subscription_attempts "
            "WHERE scope = 'ip' AND key_hash = %s",
            (ip_hash,),
        )
        row = cur.fetchone()
    assert row == (workers,)
