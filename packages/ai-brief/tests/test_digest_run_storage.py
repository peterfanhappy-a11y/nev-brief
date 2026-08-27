"""Safe persistence boundaries for digest pipeline runs."""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import psycopg
import pytest
from ai_brief import storage


def _connection(
    *,
    fetchone: tuple[Any, ...] | None,
) -> tuple[MagicMock, MagicMock]:
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False
    return connection, cursor


def test_start_digest_run_creates_one_running_record_and_returns_its_uuid() -> None:
    """Generating a second id or omitting the start timestamp breaks invocation identity."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=(run_id,))

    result = storage.start_digest_run(
        connection,
        date(2026, 8, 4),
        "gmail",
    )

    assert result == run_id
    cursor.execute.assert_called_once()
    sql, params = cursor.execute.call_args.args
    normalized_sql = " ".join(sql.split())
    assert "INSERT INTO ai_digest_runs" in normalized_sql
    assert "started_at" in normalized_sql
    assert "statement_timestamp()" in normalized_sql
    assert "RETURNING id" in normalized_sql
    assert params == (date(2026, 8, 4), "gmail", "running")


def test_finish_digest_run_records_safe_metadata_and_failure_stage() -> None:
    """Persisting caller-owned mappings verbatim could leak bodies, bytes, or credentials."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=(run_id,))
    digest_sources = {
        "events": {
            "kind": "events",
            "message_id": "<events@gmail.test>",
            "subject": "ai-events-digest-2026-08-04",
            "received_at": "2026-08-04T08:00:00+00:00",
            "requested_date": "2026-08-04",
            "matched_date": "2026-08-04",
            "used_fallback": False,
            "text": "private plain body",
            "html": "<p>private html body</p>",
            "username": "private-user",
            "password": "private-password",
            "attachments": [
                {
                    "filename": "hero.png",
                    "content_type": "image/png",
                    "size_bytes": 11,
                    "data": b"image-bytes",
                }
            ],
            "parse_count": 3,
        },
        "agent": None,
    }

    storage.finish_digest_run(
        connection,
        run_id,
        status="failed",
        digest_sources=digest_sources,
        quality_report={"passed": False, "blockers": [], "metrics": {}},
        stage="parse_agent",
        error_summary="parser rejected malformed digest",
    )

    sql, params = cursor.execute.call_args.args
    normalized_sql = " ".join(sql.split())
    assert "WITH finish_clock AS MATERIALIZED" in normalized_sql
    assert "finished_at = finish_clock.finished_at" in normalized_sql
    assert "duration_ms" in normalized_sql
    assert "status = 'running'" in normalized_sql
    assert "RETURNING run.id" in normalized_sql
    assert params[0] == "failed"
    assert json.loads(params[1]) == {
        "events": {
            "kind": "events",
            "message_id": "<events@gmail.test>",
            "subject": "ai-events-digest-2026-08-04",
            "received_at": "2026-08-04T08:00:00+00:00",
            "requested_date": "2026-08-04",
            "matched_date": "2026-08-04",
            "used_fallback": False,
            "attachments": [
                {"filename": "hero.png", "content_type": "image/png", "size_bytes": 11}
            ],
        },
        "agent": None,
    }
    assert json.loads(params[2]) == {"events": 3}
    assert json.loads(params[3]) == {"passed": False, "blockers": [], "metrics": {}}
    assert params[4:] == ("parse_agent", "digest run failed", run_id)
    persisted = " ".join(str(value) for value in params)
    for secret in (
        "private plain body",
        "private html body",
        "image-bytes",
        "private-user",
        "private-password",
    ):
        assert secret not in persisted


def test_finish_digest_run_rejects_duplicate_completion() -> None:
    """Dropping the running-state guard would let a retry overwrite terminal evidence."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=None)

    with pytest.raises(storage.DigestRunAlreadyFinishedError):
        storage.finish_digest_run(
            connection,
            run_id,
            status="completed",
            digest_sources={},
            quality_report={"passed": True},
            stage=None,
            error_summary=None,
        )

    cursor.execute.assert_called_once()


def test_finish_digest_run_redacts_credential_shaped_error_details() -> None:
    """Persisting multiline exception details could turn the summary into a raw trace."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=(run_id,))

    storage.finish_digest_run(
        connection,
        run_id,
        status="failed",
        digest_sources={},
        quality_report=None,
        stage="fetch",
        error_summary="authentication failed password=hunter2\nTraceback: private details",
    )

    params = cursor.execute.call_args.args[1]
    assert params[3] is None
    assert params[5] == "digest run failed"


def test_finish_digest_run_redacts_dsn_userinfo_from_error_summary() -> None:
    """A connection error must not persist credentials embedded in its database URI."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=(run_id,))

    storage.finish_digest_run(
        connection,
        run_id,
        status="failed",
        digest_sources={},
        quality_report=None,
        stage="storage",
        error_summary=(
            "connection to postgresql://private-user:private-password@db.test failed"
        ),
    )

    persisted_summary = cursor.execute.call_args.args[1][5]
    assert persisted_summary == "digest run failed"
    assert "private-user" not in persisted_summary
    assert "private-password" not in persisted_summary


def test_finish_digest_run_fail_closes_untrusted_quality_report_fields() -> None:
    """A nested quality report must not become a back door for raw content or credentials."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=(run_id,))
    quality_report = {
        "passed": False,
        "blockers": [
            {
                "code": "parse_failed",
                "message": "login failed for username private-user",
                "path": "today_ai",
                "text": "private plain body",
                "html": "<p>private html body</p>",
                "attachment": {"data": b"attachment-bytes"},
            }
        ],
        "warnings": [],
        "metrics": {
            "parsed_items": 3,
            "quality_passed": False,
            "username": "private-user",
            "passwordHash": "private-password-hash",
            "rawTrace": "private raw trace",
            "authorizationHeader": "Bearer private-bearer-token",
            "attachmentBytes": b"attachment-bytes",
            "free_label": "private free text",
            "nested": {
                "safe_label": "Authorization: Bearer private-bearer-token",
                "raw_trace": "File /private/runner.py line 7",
                "content": "private message body",
            },
            "listed": [1, "private listed text", {"passwordHash": "nested-secret"}],
        },
        "raw_trace": "Traceback private stack",
        "credentials": {"token": "private-token"},
    }

    storage.finish_digest_run(
        connection,
        run_id,
        status="failed",
        digest_sources={},
        quality_report=quality_report,
        stage="quality",
        error_summary=None,
    )

    persisted_report = json.loads(cursor.execute.call_args.args[1][3])
    assert persisted_report == {
        "passed": False,
        "blockers": [
            {
                "code": "parse_failed",
                "path": "today_ai",
            }
        ],
        "warnings": [],
        "metrics": {
            "parsed_items": 3,
            "quality_passed": False,
        },
    }
    serialized = json.dumps(persisted_report)
    for forbidden in (
        "private-user",
        "private-password",
        "private-password-hash",
        "private-bearer-token",
        "private raw trace",
        "private free text",
        "private listed text",
        "nested-secret",
        "private plain body",
        "private html body",
        "attachment-bytes",
        "private stack",
        "private-token",
        "/private/runner.py",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("unsafe_summary", "safe_summary"),
    [
        ("login failed username=private-user", "digest run failed"),
        ("login failed for username private-user", "digest run failed"),
        (
            "request denied Authorization: Bearer private-token",
            "digest run failed",
        ),
        ("Traceback: File /private/runner.py line 7 ValueError", "digest run failed"),
        ("worker failed at run (/private/runner.js:7:3)", "digest run failed"),
    ],
)
def test_finish_digest_run_sanitizes_single_line_error_details(
    unsafe_summary: str,
    safe_summary: str,
) -> None:
    """Single-line errors can carry credentials or raw trace details too."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=(run_id,))

    storage.finish_digest_run(
        connection,
        run_id,
        status="failed",
        digest_sources={},
        quality_report=None,
        stage="fetch",
        error_summary=unsafe_summary,
    )

    assert cursor.execute.call_args.args[1][5] == safe_summary


def test_finish_digest_run_preserves_only_controlled_error_code() -> None:
    """A stable machine code is safe to retain without accepting arbitrary caller prose."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=(run_id,))

    storage.finish_digest_run(
        connection,
        run_id,
        status="failed",
        digest_sources={},
        quality_report=None,
        stage="fetch",
        error_summary="source_timeout",
    )

    assert cursor.execute.call_args.args[1][5] == "source_timeout"


@pytest.mark.parametrize("unknown_summary", ["hunter2", "alice"])
def test_finish_digest_run_rejects_unknown_identifier_shaped_error_summary(
    unknown_summary: str,
) -> None:
    """Identifier syntax alone must not turn unknown caller text into a safe error code."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=(run_id,))

    storage.finish_digest_run(
        connection,
        run_id,
        status="failed",
        digest_sources={},
        quality_report=None,
        stage="fetch",
        error_summary=unknown_summary,
    )

    assert cursor.execute.call_args.args[1][5] == "digest run failed"


def test_finish_digest_run_drops_unknown_issue_code_path_and_metric_key() -> None:
    """Catalog membership, not harmless-looking syntax, controls quality persistence."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=(run_id,))

    storage.finish_digest_run(
        connection,
        run_id,
        status="failed",
        digest_sources={},
        quality_report={
            "passed": False,
            "blockers": [{"code": "hunter2", "message": "ignored", "path": "alice"}],
            "warnings": [],
            "metrics": {"hunter2": 1},
        },
        stage="quality",
        error_summary="quality_gate_failed",
    )

    assert json.loads(cursor.execute.call_args.args[1][3]) == {
        "passed": False,
        "blockers": [],
        "warnings": [],
        "metrics": {},
    }


@pytest.mark.parametrize("stage", [None, "", "   "])
def test_finish_failed_digest_run_requires_non_empty_stage(stage: str | None) -> None:
    """A failed run without its failed stage destroys the operational evidence."""
    run_id = UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30")
    connection, cursor = _connection(fetchone=(run_id,))

    with pytest.raises(ValueError, match="stage"):
        storage.finish_digest_run(
            connection,
            run_id,
            status="failed",
            digest_sources={},
            quality_report=None,
            stage=stage,
            error_summary="failed",
        )

    cursor.execute.assert_not_called()


def _postgres_connection() -> psycopg.Connection[Any]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for PostgreSQL integration tests")
    return psycopg.connect(database_url)


@pytest.mark.integration
def test_digest_run_lifecycle_uses_advancing_timestamps_in_one_transaction() -> None:
    """Transaction-scoped timestamps would report zero duration for real same-transaction work."""
    conn = _postgres_connection()
    try:
        run_id = storage.start_digest_run(conn, date(2026, 8, 4), "integration-test")
        with conn.cursor() as cur:
            cur.execute("SELECT pg_sleep(0.03);")

        storage.finish_digest_run(
            conn,
            run_id,
            status="failed",
            digest_sources={"events": None},
            quality_report={"passed": False, "blockers": [], "warnings": [], "metrics": {}},
            stage="parse",
            error_summary="fixture failure",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, started_at, finished_at, duration_ms, failed_stage, updated_at
                FROM ai_digest_runs
                WHERE id = %s;
                """,
                (run_id,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row[0] == "failed"
        assert row[2] > row[1]
        assert row[3] >= 20
        assert row[4] == "parse"
        assert row[5] == row[2]

        with pytest.raises(storage.DigestRunAlreadyFinishedError):
            storage.finish_digest_run(
                conn,
                run_id,
                status="failed",
                digest_sources={},
                quality_report=None,
                stage="retry",
                error_summary="must not overwrite",
            )
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.integration
@pytest.mark.parametrize("stage", [None, "", "   ", "\t\n"])
def test_database_rejects_failed_run_without_stage(stage: str | None) -> None:
    """Direct service-role SQL must not bypass the failed-stage invariant."""
    conn = _postgres_connection()
    try:
        with (
            pytest.raises(psycopg.errors.CheckViolation),
            conn.transaction(),
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO ai_digest_runs (
                    brief_date,
                    source_adapter,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    failed_stage
                ) VALUES (
                    DATE '2026-08-04',
                    'integration-test',
                    'failed',
                    statement_timestamp(),
                    statement_timestamp(),
                    0,
                    %s
                );
                """,
                (stage,),
            )
    finally:
        conn.rollback()
        conn.close()
