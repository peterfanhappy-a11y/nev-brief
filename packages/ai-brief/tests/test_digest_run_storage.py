"""Safe persistence boundaries for digest pipeline runs."""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

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
    assert "finished_at = NOW()" in normalized_sql
    assert "duration_ms" in normalized_sql
    assert "status = 'running'" in normalized_sql
    assert "RETURNING id" in normalized_sql
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
    assert params[4:] == ("parse_agent", "parser rejected malformed digest", run_id)
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
    assert params[5] == "authentication failed password=[REDACTED]"


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
    assert persisted_summary == "connection to postgresql://[REDACTED]@db.test failed"
    assert "private-user" not in persisted_summary
    assert "private-password" not in persisted_summary
