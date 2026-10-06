"""Real PostgreSQL coverage for atomic immediate subscription activation."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://nev:nev_local_dev@localhost:54322/nev_brief",
)


def _hash(label: str) -> str:
    return hashlib.sha256(f"{label}-{uuid4()}".encode()).hexdigest()


def _email(label: str) -> str:
    return f"{label}-{uuid4()}@example.com"


def _activate(
    conn: psycopg.Connection,
    email: str,
    ip_hash: str,
    utm: dict[str, str] | None = None,
) -> tuple[bool, str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT welcome_required, unsubscribe_token::text "
            "FROM activate_ai_subscription(%s, %s, %s::jsonb)",
            (email, ip_hash, Jsonb(utm or {})),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return bool(row[0]), str(row[1])


@pytest.fixture
def db() -> psycopg.Connection:
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn


@pytest.mark.integration
def test_activate_rpc_is_strict_hardened_and_service_role_only(
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
              AND procedure.proname = 'activate_ai_subscription'
            """
        )
        row = cur.fetchone()

    assert row == (
        True,
        True,
        ['search_path=""'],
        "TABLE(welcome_required boolean, unsubscribe_token uuid)",
        True,
        False,
        False,
    )


@pytest.mark.integration
@pytest.mark.parametrize("initial_status", [None, "pending_confirmation", "unsubscribed"])
def test_activate_writes_active_and_requests_one_welcome(
    db: psycopg.Connection,
    initial_status: str | None,
) -> None:
    email = _email(initial_status or "new")
    ip_hash = _hash("ip")
    old_token_hash = _hash("confirmation")
    if initial_status is not None:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_subscribers (
                    email, status, confirmation_token_hash,
                    confirmation_expires_at, unsubscribed_at
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    email,
                    initial_status,
                    old_token_hash if initial_status == "pending_confirmation" else None,
                    datetime.now(UTC) + timedelta(hours=24)
                    if initial_status == "pending_confirmation"
                    else None,
                    datetime.now(UTC) if initial_status == "unsubscribed" else None,
                ),
            )
        db.commit()

    welcome_required, unsubscribe_token = _activate(
        db,
        email,
        ip_hash,
        {"source": "launch", "medium": "email", "campaign": "growth"},
    )

    assert welcome_required is True
    assert unsubscribe_token
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT status, confirmation_token_hash, confirmation_expires_at,
                   confirmed_at IS NOT NULL, unsubscribed_at, signup_ip_hash,
                   utm_source, utm_medium, utm_campaign
            FROM ai_subscribers
            WHERE email = %s
            """,
            (email,),
        )
        row = cur.fetchone()
    assert row == (
        "active",
        None,
        None,
        True,
        None,
        ip_hash,
        "launch",
        "email",
        "growth",
    )


@pytest.mark.integration
def test_activate_leaves_an_existing_active_subscription_unchanged(
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
            RETURNING unsubscribe_token::text
            """,
            (email, confirmed_at, _hash("original-ip")),
        )
        original_token = str(cur.fetchone()[0])
    db.commit()

    welcome_required, returned_token = _activate(
        db,
        email,
        _hash("new-ip"),
        {"source": "replacement", "medium": "paid", "campaign": "summer"},
    )

    assert welcome_required is False
    assert returned_token == original_token
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT confirmed_at, utm_source, utm_medium, utm_campaign
            FROM ai_subscribers
            WHERE email = %s
            """,
            (email,),
        )
        row = cur.fetchone()
    assert row == (confirmed_at, "original", "referral", "spring")


@pytest.mark.integration
def test_concurrent_activation_requests_only_one_welcome(
    db: psycopg.Connection,
) -> None:
    email = _email("concurrent")

    def activate_once(label: str) -> bool:
        with psycopg.connect(DATABASE_URL) as conn:
            return _activate(conn, email, _hash(label))[0]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(activate_once, ["first", "second"]))

    assert sorted(results) == [False, True]
    with db.cursor() as cur:
        cur.execute(
            "SELECT count(*), min(status) FROM ai_subscribers WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()
    assert row == (1, "active")
