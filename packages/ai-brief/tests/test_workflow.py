"""Atomic generation, approval, and release workflow state machine."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import psycopg
import pytest
from ai_brief import composer, runner, storage
from ai_brief.digest.input import DigestEnvelope
from ai_brief.quality import QualityIssue, QualityReport
from ai_brief.schema import AiBriefContent, DigestSection, DigestStory, Theme

BRIEF_DATE = date(2026, 8, 4)
RUN_ID = UUID("aee85a2c-9c58-4be9-8a30-d4aed5fa4690")


def _section(theme: Theme, *, header_image: str | None = "https://img.test/x.jpg") -> DigestSection:
    return DigestSection(
        theme=theme,
        header_image=header_image,
        stories=[
            DigestStory(
                headline=f"Story {index}",
                summary="Useful summary",
                url=f"https://openai.com/story-{index}",
            )
            for index in range(3)
        ],
    )


def _bundle() -> SimpleNamespace:
    return SimpleNamespace(
        subject="A safe review candidate",
        preheader="Three important updates",
        editorial="A concise editorial for human review.",
        intro_bullets=["One", "Two"],
        today_ai=_section(Theme.MODEL_RESEARCH),
        ai_masters=_section(Theme.PRODUCT_TOOLS),
        ai_research=_section(Theme.AI_RESEARCH),
        ai_engineering=_section(Theme.AI_ENGINEERING),
        agent_tools=_section(Theme.AGENT_TOOLS, header_image=None),
        deepseek_complete=True,
        qwen_complete=True,
    )


def _quality(*, passed: bool) -> QualityReport:
    blockers = () if passed else (QualityIssue("subject_blank", "unsafe detail", "subject"),)
    return QualityReport(
        passed=passed,
        blockers=blockers,
        warnings=(),
        metrics={"quality_passed": passed, "blocker_count": len(blockers)},
    )


def _connection() -> MagicMock:
    connection = MagicMock()
    connection.commit.return_value = None
    connection.rollback.return_value = None
    return connection


class _Adapter:
    def __init__(self) -> None:
        self.fetch_calls = 0

    def fetch(self, brief_date: date) -> dict[str, None]:
        self.fetch_calls += 1
        assert brief_date == BRIEF_DATE
        return {
            "events": None,
            "builder": None,
            "research": None,
            "engineering": None,
            "agent": None,
        }


@pytest.mark.parametrize(
    ("passed", "expected_status"),
    [(False, "blocked"), (True, "awaiting_approval")],
)
async def test_generation_quality_result_controls_review_state(
    passed: bool,
    expected_status: str,
) -> None:
    connection = _connection()
    adapter = _Adapter()
    report = _quality(passed=passed)
    build = AsyncMock(return_value=_bundle())

    with (
        patch.object(storage, "start_digest_run", return_value=RUN_ID),
        patch.object(storage, "claim_brief_generation", return_value="started"),
        patch.object(storage, "fetch_previous_brief", return_value=None),
        patch.object(storage, "save_generated_brief") as save,
        patch.object(storage, "finish_digest_run") as finish,
        patch.object(runner, "build_digest_modules", build),
        patch.object(runner, "validate_brief", return_value=report),
        patch.object(runner, "_alert") as alert,
        patch.object(composer, "compose_for_date") as compose,
    ):
        result = await runner.generate_for_review(connection, BRIEF_DATE, adapter)

    assert result.status == expected_status
    assert result.exit_code == (0 if passed else 1)
    assert adapter.fetch_calls == 1
    build.assert_awaited_once()
    assert save.call_args.kwargs["status"] == expected_status
    assert save.call_args.kwargs["source_run_id"] == RUN_ID
    assert finish.call_args.kwargs["status"] == expected_status
    compose.assert_not_called()
    if passed:
        alert.assert_not_called()
    else:
        alert.assert_called_once()


async def test_generation_passes_explicit_model_outcomes_to_quality_gate() -> None:
    connection = _connection()
    adapter = _Adapter()
    bundle = _bundle()
    bundle.deepseek_complete = False
    bundle.qwen_complete = False
    validate = MagicMock(return_value=_quality(passed=False))
    with (
        patch.object(storage, "start_digest_run", return_value=RUN_ID),
        patch.object(storage, "claim_brief_generation", return_value="started"),
        patch.object(storage, "fetch_previous_brief", return_value=None),
        patch.object(storage, "save_generated_brief"),
        patch.object(storage, "finish_digest_run"),
        patch.object(runner, "build_digest_modules", AsyncMock(return_value=bundle)),
        patch.object(runner, "validate_brief", validate),
        patch.object(runner, "_alert"),
    ):
        await runner.generate_for_review(connection, BRIEF_DATE, adapter)

    assert validate.call_args.kwargs["deepseek_complete"] is False
    assert validate.call_args.kwargs["qwen_complete"] is False


def test_generation_claim_binds_owner_and_rejects_an_active_generating_row() -> None:
    connection = _connection()
    cursor = MagicMock()
    cursor.fetchone.return_value = ("generating",)
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False

    assert storage.claim_brief_generation(connection, BRIEF_DATE, RUN_ID) == "started"
    sql, params = cursor.execute.call_args.args
    normalized = " ".join(sql.split())
    assert "source_run_id" in normalized
    assert "status IN ('blocked', 'awaiting_approval')" in normalized
    assert "status IN ('generating'" not in normalized
    assert params == (BRIEF_DATE, RUN_ID)


def test_generation_finalize_and_failure_are_owner_compare_and_swap_operations() -> None:
    connection = _connection()
    cursor = MagicMock()
    cursor.fetchone.return_value = ("brief-id",)
    cursor.rowcount = 0
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False

    storage.save_generated_brief(
        connection,
        brief_date=BRIEF_DATE,
        content={"subject": "owned"},
        model="model",
        digest_sources={},
        quality_report=_safe_report(True),
        source_run_id=RUN_ID,
        status="awaiting_approval",
    )
    save_sql = " ".join(cursor.execute.call_args.args[0].split())
    assert "status = 'generating'" in save_sql
    assert "source_run_id = %s" in save_sql
    assert cursor.execute.call_args.args[1][-2:] == (BRIEF_DATE, RUN_ID)

    assert storage.mark_brief_generation_failed(connection, BRIEF_DATE, RUN_ID) is False
    fail_sql = " ".join(cursor.execute.call_args.args[0].split())
    assert "status = 'generating'" in fail_sql
    assert "source_run_id = %s" in fail_sql
    assert cursor.execute.call_args.args[1] == (BRIEF_DATE, RUN_ID)


async def test_generation_conflicts_before_adapter_or_model_calls() -> None:
    connection = _connection()
    adapter = _Adapter()
    build = AsyncMock()
    with (
        patch.object(storage, "start_digest_run", return_value=RUN_ID),
        patch.object(storage, "claim_brief_generation", return_value="conflict"),
        patch.object(storage, "finish_digest_run") as finish,
        patch.object(runner, "build_digest_modules", build),
    ):
        result = await runner.generate_for_review(connection, BRIEF_DATE, adapter)

    assert result.status == "conflict"
    assert result.exit_code == 1
    assert adapter.fetch_calls == 0
    build.assert_not_awaited()
    assert finish.call_args.kwargs == {
        "status": "failed",
        "digest_sources": {},
        "quality_report": None,
        "stage": "state",
        "error_summary": "brief_generation_failed",
    }


async def test_generation_exception_records_safe_failed_run_without_partial_content() -> None:
    connection = _connection()
    raw_secret = "password=hunter2 raw message body"  # noqa: S105 - inert leak sentinel
    envelope = DigestEnvelope(
        kind="events",
        message_id="safe-message-id",
        subject="safe subject",
        received_at=datetime(2026, 8, 4, tzinfo=UTC),
        requested_date=BRIEF_DATE,
        matched_date=BRIEF_DATE,
        used_fallback=False,
        text=raw_secret,
        html=f"<p>{raw_secret}</p>",
        attachments=(),
    )
    adapter = MagicMock()
    adapter.fetch.return_value = {
        "events": envelope,
        "builder": None,
        "research": None,
        "engineering": None,
        "agent": None,
    }
    with (
        patch.object(storage, "start_digest_run", return_value=RUN_ID),
        patch.object(storage, "claim_brief_generation", return_value="started"),
        patch.object(storage, "fetch_previous_brief", return_value=None),
        patch.object(storage, "mark_brief_generation_failed") as mark_brief_failed,
        patch.object(storage, "finish_digest_run") as finish,
        patch.object(
            runner,
            "build_digest_modules",
            AsyncMock(side_effect=RuntimeError(raw_secret)),
        ),
        patch.object(runner, "_alert") as alert,
    ):
        result = await runner.generate_for_review(connection, BRIEF_DATE, adapter)

    assert result.status == "failed"
    assert result.exit_code == 1
    connection.rollback.assert_called()
    mark_brief_failed.assert_called_once_with(connection, BRIEF_DATE, RUN_ID)
    assert finish.call_args.kwargs["error_summary"] == "brief_generation_failed"
    assert finish.call_args.kwargs["digest_sources"]["events"] == envelope.metadata()
    persisted = repr(finish.call_args) + repr(alert.call_args)
    assert raw_secret not in persisted


async def test_start_run_failure_rolls_back_and_alerts_without_raw_details() -> None:
    connection = _connection()
    raw_secret = "postgresql://user:password@db/private"  # noqa: S105
    with (
        patch.object(storage, "start_digest_run", side_effect=RuntimeError(raw_secret)),
        patch.object(runner, "_alert") as alert,
        pytest.raises(RuntimeError, match="postgresql"),
    ):
        await runner.generate_for_review(connection, BRIEF_DATE, _Adapter())

    connection.rollback.assert_called_once_with()
    alert.assert_called_once()
    assert raw_secret not in repr(alert.call_args)


async def test_first_run_commit_failure_rolls_back_and_alerts() -> None:
    connection = _connection()
    connection.commit.side_effect = RuntimeError("commit failed private detail")
    with (
        patch.object(storage, "start_digest_run", return_value=RUN_ID),
        patch.object(runner, "_alert") as alert,
        pytest.raises(RuntimeError, match="commit failed"),
    ):
        await runner.generate_for_review(connection, BRIEF_DATE, _Adapter())

    connection.rollback.assert_called_once_with()
    alert.assert_called_once()
    assert "private detail" not in repr(alert.call_args)


async def test_failed_run_recording_failure_alerts_before_reraising() -> None:
    connection = _connection()
    raw_secret = "failure recording password=hunter2"  # noqa: S105
    with (
        patch.object(storage, "start_digest_run", return_value=RUN_ID),
        patch.object(storage, "claim_brief_generation", return_value="started"),
        patch.object(storage, "fetch_previous_brief", return_value=None),
        patch.object(storage, "mark_brief_generation_failed"),
        patch.object(storage, "finish_digest_run", side_effect=RuntimeError(raw_secret)),
        patch.object(
            runner,
            "build_digest_modules",
            AsyncMock(side_effect=RuntimeError("model failed")),
        ),
        patch.object(runner, "_alert") as alert,
        pytest.raises(RuntimeError, match="failure recording"),
    ):
        await runner.generate_for_review(connection, BRIEF_DATE, _Adapter())

    assert connection.rollback.call_count >= 2
    alert.assert_called_once()
    assert raw_secret not in repr(alert.call_args)


async def test_schema_invalid_candidate_is_quality_blocked_not_pipeline_failed() -> None:
    connection = _connection()
    adapter = _Adapter()
    invalid_bundle = _bundle()
    invalid_bundle.intro_bullets = []
    invalid_bundle.today_ai = None
    with (
        patch.object(storage, "start_digest_run", return_value=RUN_ID),
        patch.object(storage, "claim_brief_generation", return_value="started"),
        patch.object(storage, "fetch_previous_brief", return_value=None),
        patch.object(storage, "save_generated_brief") as save,
        patch.object(storage, "finish_digest_run") as finish,
        patch.object(storage, "mark_brief_generation_failed") as mark_failed,
        patch.object(runner, "build_digest_modules", AsyncMock(return_value=invalid_bundle)),
        patch.object(runner, "_alert"),
    ):
        result = await runner.generate_for_review(connection, BRIEF_DATE, adapter)

    assert result.status == "blocked"
    assert result.quality_report is not None
    assert "schema_invalid" in {issue.code for issue in result.quality_report.blockers}
    assert save.call_args.kwargs["status"] == "blocked"
    assert finish.call_args.kwargs["status"] == "blocked"
    mark_failed.assert_not_called()


@pytest.mark.parametrize(
    ("status", "report", "expected_status", "changed"),
    [
        ("awaiting_approval", {"passed": True}, "approved", True),
        ("awaiting_approval", {"passed": False}, "awaiting_approval", False),
        ("blocked", {"passed": True}, "blocked", False),
        ("approved", {"passed": True}, "approved", False),
        ("published", {"passed": True}, "published", False),
    ],
)
def test_approval_requires_awaiting_brief_with_stored_passing_report(
    status: str,
    report: dict[str, bool],
    expected_status: str,
    changed: bool,
) -> None:
    connection = _connection()
    locked = SimpleNamespace(status=status, quality_report=report)
    with (
        patch.object(storage, "lock_brief_for_approval", return_value=locked),
        patch.object(storage, "approve_locked_brief") as approve,
        patch.object(composer, "compose_for_date") as compose,
    ):
        result = runner.approve_brief(connection, BRIEF_DATE, approved_by="local-operator")

    assert result.status == expected_status
    assert result.changed is changed
    assert result.exit_code == (0 if changed else 1)
    assert approve.call_count == int(changed)
    compose.assert_not_called()


@pytest.mark.parametrize("bad_operator", ["", "  ", "\t\n"])
def test_approval_rejects_blank_operator_identifier(bad_operator: str) -> None:
    with pytest.raises(ValueError, match="approved_by"):
        runner.approve_brief(_connection(), BRIEF_DATE, approved_by=bad_operator)


@pytest.mark.parametrize("status", ["generating", "blocked", "awaiting_approval"])
def test_release_from_unapproved_state_is_nonzero_noop_and_alerts(status: str) -> None:
    connection = _connection()
    locked = SimpleNamespace(status=status, content={}, source_run_id=RUN_ID)
    with (
        patch.object(storage, "lock_brief_for_release", return_value=locked),
        patch.object(composer, "compose_frozen_brief") as compose,
        patch.object(storage, "publish_locked_brief_and_complete_run") as publish,
        patch.object(runner, "_alert") as alert,
    ):
        result = runner.release_approved(connection, BRIEF_DATE)

    assert result.released is False
    assert result.exit_code == 1
    assert result.reason == "not_approved"
    compose.assert_not_called()
    publish.assert_not_called()
    alert.assert_called_once()
    connection.rollback.assert_called_once_with()


def test_approved_brief_releases_exactly_once_and_rerun_is_idempotent() -> None:
    connection = _connection()
    approved = SimpleNamespace(
        status="approved", content={"subject": "Frozen"}, source_run_id=RUN_ID
    )
    published = SimpleNamespace(
        status="published", content={"subject": "Frozen"}, source_run_id=RUN_ID
    )
    with (
        patch.object(storage, "lock_brief_for_release", side_effect=[approved, published]),
        patch.object(composer, "compose_frozen_brief", return_value={"composed": 2}) as compose,
        patch.object(storage, "publish_locked_brief_and_complete_run") as publish,
    ):
        first = runner.release_approved(connection, BRIEF_DATE)
        second = runner.release_approved(connection, BRIEF_DATE)

    assert first.released is True
    assert first.status == "published"
    assert first.composed == 2
    assert first.exit_code == 0
    assert second.released is False
    assert second.reason == "already_published"
    assert second.exit_code == 0
    compose.assert_called_once_with(
        connection,
        BRIEF_DATE,
        {"subject": "Frozen"},
        only_email=None,
    )
    publish.assert_called_once_with(connection, BRIEF_DATE, source_run_id=RUN_ID)


def test_release_rolls_back_delivery_inserts_when_publication_fails() -> None:
    connection = _connection()
    approved = SimpleNamespace(
        status="approved", content={"subject": "Frozen"}, source_run_id=RUN_ID
    )
    with (
        patch.object(storage, "lock_brief_for_release", return_value=approved),
        patch.object(composer, "compose_frozen_brief", return_value={"composed": 1}),
        patch.object(
            storage,
            "publish_locked_brief_and_complete_run",
            side_effect=RuntimeError("database write failed"),
        ),
        patch.object(runner, "_alert"),
        pytest.raises(RuntimeError, match="database write failed"),
    ):
        runner.release_approved(connection, BRIEF_DATE)

    connection.rollback.assert_called_once_with()


def test_legacy_compose_cannot_create_deliveries_outside_release() -> None:
    connection = _connection()
    with (
        patch.object(storage, "fetch_brief") as fetch,
        patch.object(storage, "fetch_active_subscribers") as subscribers,
        pytest.raises(RuntimeError, match="release_approved"),
    ):
        composer.compose_for_date(connection, BRIEF_DATE)

    fetch.assert_not_called()
    subscribers.assert_not_called()


def test_late_explicit_release_succeeds_after_approval() -> None:
    connection = _connection()
    approved = SimpleNamespace(status="approved", content={"subject": "Late"}, source_run_id=RUN_ID)
    with (
        patch.object(storage, "lock_brief_for_release", return_value=approved),
        patch.object(composer, "compose_frozen_brief", return_value={"composed": 1}),
        patch.object(storage, "publish_locked_brief_and_complete_run"),
    ):
        result = runner.release_approved(connection, BRIEF_DATE, only_email="late@example.test")

    assert datetime.now(UTC).date() >= BRIEF_DATE
    assert result.released is True
    assert result.status == "published"


def _postgres_connection() -> psycopg.Connection[Any]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for PostgreSQL integration tests")
    return psycopg.connect(database_url)


def _brief_content(brief_date: date) -> dict[str, Any]:
    return AiBriefContent(
        brief_date=brief_date.isoformat(),
        subject="Frozen workflow candidate",
        preheader="Review before release",
        editorial="This content is frozen at approval.",
        intro_bullets=["One", "Two"],
        today_ai=_section(Theme.MODEL_RESEARCH),
        ai_masters=_section(Theme.PRODUCT_TOOLS),
        ai_research=_section(Theme.AI_RESEARCH),
        ai_engineering=_section(Theme.AI_ENGINEERING),
        agent_tools=_section(Theme.AGENT_TOOLS, header_image=None),
        model="integration-model",
    ).model_dump(mode="json")


def _safe_report(passed: bool) -> dict[str, Any]:
    blockers = [] if passed else [{"code": "subject_blank", "path": "subject"}]
    return {
        "passed": passed,
        "blockers": blockers,
        "warnings": [],
        "metrics": {"quality_passed": passed, "blocker_count": len(blockers)},
    }


def _seed_generated_brief(
    conn: psycopg.Connection[Any],
    brief_date: date,
    *,
    passed: bool,
) -> UUID:
    run_id = storage.start_digest_run(conn, brief_date, "integration-test")
    conn.commit()
    assert storage.claim_brief_generation(conn, brief_date, run_id) == "started"
    report = _safe_report(passed)
    status = "awaiting_approval" if passed else "blocked"
    storage.save_generated_brief(
        conn,
        brief_date=brief_date,
        content=_brief_content(brief_date),
        model="integration-model",
        digest_sources={},
        quality_report=report,
        source_run_id=run_id,
        status=status,
    )
    storage.finish_digest_run(
        conn,
        run_id,
        status=status,
        digest_sources={},
        quality_report=report,
        stage="quality" if not passed else None,
        error_summary="quality_gate_failed" if not passed else None,
    )
    conn.commit()
    return run_id


def _insert_active_subscriber(conn: psycopg.Connection[Any], email: str) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ai_subscribers (email, status, confirmed_at, source)
            VALUES (%s, 'active', statement_timestamp(), 'test')
            RETURNING id;
            """,
            (email,),
        )
        row = cur.fetchone()
    assert row is not None
    conn.commit()
    return row[0]


def _cleanup_workflow_fixtures(
    conn: psycopg.Connection[Any],
    dates: list[date],
    emails: list[str],
) -> None:
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM ai_deliveries WHERE brief_date = ANY(%s::date[]);", (dates,))
        cur.execute("DELETE FROM ai_daily_briefs WHERE brief_date = ANY(%s::date[]);", (dates,))
        cur.execute("DELETE FROM ai_digest_runs WHERE brief_date = ANY(%s::date[]);", (dates,))
        cur.execute("DELETE FROM ai_subscribers WHERE email = ANY(%s::text[]);", (emails,))
    conn.commit()


@pytest.mark.integration
def test_postgres_generation_claim_has_one_owner_and_rejects_stale_worker() -> None:
    brief_date = date(2096, 8, 9)
    first = _postgres_connection()
    second = _postgres_connection()
    try:
        _cleanup_workflow_fixtures(first, [brief_date], [])
        first_run = storage.start_digest_run(first, brief_date, "first-worker")
        first.commit()
        second_run = storage.start_digest_run(second, brief_date, "second-worker")
        second.commit()

        assert storage.claim_brief_generation(first, brief_date, first_run) == "started"
        first.commit()
        assert storage.claim_brief_generation(second, brief_date, second_run) == "conflict"
        second.rollback()
        with first.cursor() as cur:
            cur.execute(
                "SELECT status, source_run_id FROM ai_daily_briefs WHERE brief_date = %s;",
                (brief_date,),
            )
            assert cur.fetchone() == ("generating", first_run)
        first.commit()

        assert storage.mark_brief_generation_failed(first, brief_date, first_run) is True
        first.commit()
        assert storage.claim_brief_generation(second, brief_date, second_run) == "started"
        second.commit()

        with pytest.raises(storage.WorkflowTransitionError, match="disappeared"):
            storage.save_generated_brief(
                first,
                brief_date=brief_date,
                content=_brief_content(brief_date),
                model="stale-model",
                digest_sources={},
                quality_report=_safe_report(True),
                source_run_id=first_run,
                status="awaiting_approval",
            )
        first.rollback()
        assert storage.mark_brief_generation_failed(first, brief_date, first_run) is False
        first.rollback()

        storage.save_generated_brief(
            second,
            brief_date=brief_date,
            content=_brief_content(brief_date),
            model="current-model",
            digest_sources={},
            quality_report=_safe_report(True),
            source_run_id=second_run,
            status="awaiting_approval",
        )
        second.commit()
        with second.cursor() as cur:
            cur.execute(
                "SELECT status, source_run_id, model FROM ai_daily_briefs WHERE brief_date = %s;",
                (brief_date,),
            )
            assert cur.fetchone() == ("awaiting_approval", second_run, "current-model")
    finally:
        second.rollback()
        second.close()
        _cleanup_workflow_fixtures(first, [brief_date], [])
        first.close()


@pytest.mark.integration
def test_postgres_approval_requires_state_and_boolean_passing_report() -> None:
    brief_date = date(2096, 8, 4)
    conn = _postgres_connection()
    try:
        _cleanup_workflow_fixtures(conn, [brief_date], [])
        _seed_generated_brief(conn, brief_date, passed=False)

        blocked = runner.approve_brief(conn, brief_date, approved_by="integration-operator")
        assert blocked.changed is False
        assert blocked.status == "blocked"

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ai_daily_briefs
                SET status = 'awaiting_approval', quality_report = '{"passed":"true"}'::jsonb
                WHERE brief_date = %s;
                """,
                (brief_date,),
            )
        conn.commit()
        string_true = runner.approve_brief(
            conn, brief_date, approved_by="integration-operator"
        )
        assert string_true.changed is False

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ai_daily_briefs
                SET quality_report = '{"passed":true}'::jsonb
                WHERE brief_date = %s;
                """,
                (brief_date,),
            )
        conn.commit()
        approved = runner.approve_brief(conn, brief_date, approved_by="integration-operator")
        assert approved.changed is True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, approved_by, approved_at IS NOT NULL
                FROM ai_daily_briefs WHERE brief_date = %s;
                """,
                (brief_date,),
            )
            assert cur.fetchone() == ("approved", "integration-operator", True)
    finally:
        _cleanup_workflow_fixtures(conn, [brief_date], [])
        conn.close()


@pytest.mark.integration
def test_postgres_release_lock_and_idempotent_delivery_creation() -> None:
    brief_date = date(2096, 8, 5)
    email = "task4-idempotent@example.test"
    conn = _postgres_connection()
    contender = _postgres_connection()
    try:
        _cleanup_workflow_fixtures(conn, [brief_date], [email])
        _insert_active_subscriber(conn, email)
        _seed_generated_brief(conn, brief_date, passed=True)
        assert runner.approve_brief(
            conn, brief_date, approved_by="integration-operator"
        ).changed

        locked = storage.lock_brief_for_release(conn, brief_date)
        assert locked is not None and locked.status == "approved"
        with (
            pytest.raises(psycopg.errors.LockNotAvailable),
            contender.transaction(),
            contender.cursor() as cur,
        ):
            cur.execute(
                """
                SELECT id FROM ai_daily_briefs
                WHERE brief_date = %s
                FOR UPDATE NOWAIT;
                """,
                (brief_date,),
            )
        conn.rollback()

        first = runner.release_approved(conn, brief_date, only_email=email)
        second = runner.release_approved(conn, brief_date, only_email=email)
        assert (first.released, first.composed, first.exit_code) == (True, 1, 0)
        assert (second.released, second.composed, second.exit_code) == (False, 0, 0)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT brief.status, brief.published_at IS NOT NULL, run.status,
                       count(delivery.id)
                FROM ai_daily_briefs AS brief
                JOIN ai_digest_runs AS run ON run.id = brief.source_run_id
                LEFT JOIN ai_deliveries AS delivery ON delivery.brief_date = brief.brief_date
                WHERE brief.brief_date = %s
                GROUP BY brief.status, brief.published_at, run.status;
                """,
                (brief_date,),
            )
            assert cur.fetchone() == ("published", True, "completed", 1)
    finally:
        contender.rollback()
        contender.close()
        _cleanup_workflow_fixtures(conn, [brief_date], [email])
        conn.close()


@pytest.mark.integration
@pytest.mark.parametrize("existing_status", ["sent", "failed"])
def test_postgres_release_never_rewrites_existing_terminal_delivery(
    existing_status: str,
) -> None:
    day = 6 if existing_status == "sent" else 7
    brief_date = date(2096, 8, day)
    email = f"task4-{existing_status}@example.test"
    conn = _postgres_connection()
    try:
        _cleanup_workflow_fixtures(conn, [brief_date], [email])
        subscriber_id = _insert_active_subscriber(conn, email)
        _seed_generated_brief(conn, brief_date, passed=True)
        assert runner.approve_brief(
            conn, brief_date, approved_by="integration-operator"
        ).changed
        delivery_id = uuid4()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_deliveries (
                    id, subscriber_id, brief_date, subject, content_html, content_text,
                    status, resend_id, error, retry_count, sent_at
                ) VALUES (%s, %s, %s, 'frozen subject', 'frozen html', 'frozen text',
                          %s, %s, %s, 3,
                          CASE WHEN %s = 'sent' THEN statement_timestamp() ELSE NULL END);
                """,
                (
                    delivery_id,
                    subscriber_id,
                    brief_date,
                    existing_status,
                    "resend-frozen" if existing_status == "sent" else None,
                    "frozen failure" if existing_status == "failed" else None,
                    existing_status,
                ),
            )
        conn.commit()

        released = runner.release_approved(conn, brief_date, only_email=email)
        assert released.released is True
        assert released.composed == 0
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, subject, content_html, content_text, status, resend_id, error,
                       retry_count
                FROM ai_deliveries
                WHERE subscriber_id = %s AND brief_date = %s;
                """,
                (subscriber_id, brief_date),
            )
            assert cur.fetchone() == (
                delivery_id,
                "frozen subject",
                "frozen html",
                "frozen text",
                existing_status,
                "resend-frozen" if existing_status == "sent" else None,
                "frozen failure" if existing_status == "failed" else None,
                3,
            )
    finally:
        _cleanup_workflow_fixtures(conn, [brief_date], [email])
        conn.close()


@pytest.mark.integration
def test_postgres_release_rolls_back_insert_when_linked_run_cannot_complete() -> None:
    brief_date = date(2096, 8, 8)
    email = "task4-rollback@example.test"
    conn = _postgres_connection()
    try:
        _cleanup_workflow_fixtures(conn, [brief_date], [email])
        _insert_active_subscriber(conn, email)
        run_id = _seed_generated_brief(conn, brief_date, passed=True)
        assert runner.approve_brief(
            conn, brief_date, approved_by="integration-operator"
        ).changed
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ai_digest_runs SET status = 'blocked' WHERE id = %s;",
                (run_id,),
            )
        conn.commit()

        with (
            patch.object(runner, "_alert"),
            pytest.raises(storage.WorkflowTransitionError, match="completion failed"),
        ):
            runner.release_approved(conn, brief_date, only_email=email)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT brief.status, brief.published_at, run.status,
                       count(delivery.id)
                FROM ai_daily_briefs AS brief
                JOIN ai_digest_runs AS run ON run.id = brief.source_run_id
                LEFT JOIN ai_deliveries AS delivery ON delivery.brief_date = brief.brief_date
                WHERE brief.brief_date = %s
                GROUP BY brief.status, brief.published_at, run.status;
                """,
                (brief_date,),
            )
            assert cur.fetchone() == ("approved", None, "blocked", 0)
    finally:
        _cleanup_workflow_fixtures(conn, [brief_date], [email])
        conn.close()
