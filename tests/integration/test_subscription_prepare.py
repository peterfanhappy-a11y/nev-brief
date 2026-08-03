"""Real PostgreSQL coverage for atomic pending subscription preparation."""

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import psycopg
import pytest

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://nev:nev_local_dev@localhost:54322/nev_brief",
)


def _hash(label: str) -> str:
    return hashlib.sha256(f"{label}-{uuid4()}".encode()).hexdigest()


def _email(label: str) -> str:
    return f"{label}-{uuid4()}@example.com"


def _prepare(
    conn: psycopg.Connection,
    email: str,
    token_hash: str,
    expires_at: datetime,
    ip_hash: str,
    utm: dict[str, str] | None = None,
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT confirmation_required "
            "FROM prepare_ai_subscription(%s, %s, %s, %s, %s::jsonb)",
            (email, token_hash, expires_at, ip_hash, utm or {}),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return bool(row[0])


@pytest.fixture
def db() -> psycopg.Connection:
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn


@pytest.mark.integration
def test_prepare_rpc_is_strict_hardened_service_role_only_and_boolean_only(
    db: psycopg.Connection,
) -> None:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT procedure.prosecdef,
                   procedure.proisstrict,
                   procedure.proconfig,
                   pg_get_function_result(procedure.oid),
                   has_function_privilege('service_role', procedure.oid, 'EXECUTE'),
                   has_function_privilege('anon', procedure.oid, 'EXECUTE'),
                   has_function_privilege('authenticated', procedure.oid, 'EXECUTE')
            FROM pg_proc AS procedure
            JOIN pg_namespace AS namespace
              ON namespace.oid = procedure.pronamespace
            WHERE namespace.nspname = 'public'
              AND procedure.proname = 'prepare_ai_subscription'
            """
        )
        row = cur.fetchone()

    assert row == (
        True,
        True,
        ['search_path=""'],
        "TABLE(confirmation_required boolean)",
        True,
        False,
        False,
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("initial_status", "expected_confirmation"),
    [(None, True), ("pending_confirmation", True), ("unsubscribed", True)],
)
def test_prepare_returns_true_and_writes_pending_for_confirmable_states(
    db: psycopg.Connection,
    initial_status: str | None,
    expected_confirmation: bool,
) -> None:
    email = _email(initial_status or "new")
    old_hash = _hash("old-token")
    new_hash = _hash("new-token")
    ip_hash = _hash("ip")
    expires_at = datetime.now(UTC) + timedelta(hours=24)
    if initial_status is not None:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_subscribers (
                    email, status, confirmation_token_hash,
                    confirmation_expires_at, unsubscribed_at,
                    signup_ip_hash, utm_source
                ) VALUES (%s, %s, %s, %s, %s, %s, 'old-source')
                """,
                (
                    email,
                    initial_status,
                    old_hash if initial_status == "pending_confirmation" else None,
                    expires_at if initial_status == "pending_confirmation" else None,
                    datetime.now(UTC) if initial_status == "unsubscribed" else None,
                    _hash("old-ip"),
                ),
            )
        db.commit()

    result = _prepare(
        db,
        email,
        new_hash,
        expires_at,
        ip_hash,
        {"source": "launch", "medium": "email", "campaign": "phase-1"},
    )

    assert result is expected_confirmation
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT status, confirmation_token_hash, confirmation_expires_at,
                   confirmed_at, unsubscribed_at, signup_ip_hash,
                   utm_source, utm_medium, utm_campaign
            FROM ai_subscribers
            WHERE email = %s
            """,
            (email,),
        )
        row = cur.fetchone()
    assert row == (
        "pending_confirmation",
        new_hash,
        expires_at,
        None,
        None,
        ip_hash,
        "launch",
        "email",
        "phase-1",
    )


@pytest.mark.integration
def test_prepare_returns_false_and_leaves_every_active_field_unchanged(
    db: psycopg.Connection,
) -> None:
    email = _email("active")
    confirmed_at = datetime.now(UTC) - timedelta(days=2)
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ai_subscribers (
                email, status, confirmed_at, signup_ip_hash,
                utm_source, utm_medium, utm_campaign
            ) VALUES (%s, 'active', %s, %s, 'original', 'referral', 'spring')
            RETURNING *
            """,
            (email, confirmed_at, _hash("original-ip")),
        )
        before = cur.fetchone()
    db.commit()

    result = _prepare(
        db,
        email,
        _hash("new-token"),
        datetime.now(UTC) + timedelta(hours=24),
        _hash("new-ip"),
        {"source": "replacement", "medium": "paid", "campaign": "summer"},
    )

    assert result is False
    with db.cursor() as cur:
        cur.execute("SELECT * FROM ai_subscribers WHERE email = %s", (email,))
        after = cur.fetchone()
    assert after == before


@pytest.mark.integration
def test_prepare_waiting_on_confirmation_cannot_downgrade_the_committed_active_row(
    db: psycopg.Connection,
) -> None:
    email = _email("concurrent")
    old_hash = _hash("confirm-token")
    expires_at = datetime.now(UTC) + timedelta(hours=24)
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ai_subscribers (
                email, status, confirmation_token_hash, confirmation_expires_at
            ) VALUES (%s, 'pending_confirmation', %s, %s)
            """,
            (email, old_hash, expires_at),
        )
    db.commit()

    app_name = f"prepare-confirm-{uuid4()}"
    started = Event()

    def blocked_prepare() -> bool:
        with psycopg.connect(DATABASE_URL, application_name=app_name) as conn:
            started.set()
            return _prepare(
                conn,
                email,
                _hash("replacement-token"),
                expires_at,
                _hash("replacement-ip"),
            )

    with db.cursor() as cur:
        cur.execute("SELECT id FROM ai_subscribers WHERE email = %s FOR UPDATE", (email,))

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(blocked_prepare)
        assert started.wait(timeout=5)

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with (
                psycopg.connect(DATABASE_URL) as observer,
                observer.cursor() as cur,
            ):
                cur.execute(
                    """
                    SELECT wait_event_type
                    FROM pg_stat_activity
                    WHERE application_name = %s
                      AND query LIKE '%%prepare_ai_subscription%%'
                    """,
                    (app_name,),
                )
                activity = cur.fetchone()
            if activity == ("Lock",):
                break
            time.sleep(0.01)
        else:
            pytest.fail("concurrent prepare call did not block on the subscriber row")

        with db.cursor() as cur:
            cur.execute(
                "SELECT id FROM confirm_ai_subscription(%s, %s)",
                (old_hash, datetime.now(UTC)),
            )
            assert cur.fetchone() is not None
        db.commit()

        assert future.result(timeout=5) is False

    with db.cursor() as cur:
        cur.execute(
            "SELECT status, confirmation_token_hash, confirmation_expires_at "
            "FROM ai_subscribers WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()
    assert row == ("active", None, None)
