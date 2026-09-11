"""CLI workflow contract tests for Phase 3 Task 6."""

from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from ai_brief.cli import _build_parser, _cmd_daily, _cmd_generate


def test_cli_parser_exposes_review_workflow_commands() -> None:
    parser = _build_parser()
    assert parser.parse_args(["generate", "--date", "2026-08-12"]).cmd == "generate"
    assert parser.parse_args(["generate", "--date", "2026-08-12", "--backfill"]).backfill is True
    assert parser.parse_args(["preview-url", "--date", "2026-08-12"]).cmd == "preview-url"
    assert parser.parse_args(["approve", "--date", "2026-08-12"]).cmd == "approve"
    assert parser.parse_args(["release", "--date", "2026-08-12"]).cmd == "release"
    assert parser.parse_args(["stats", "--json"]).cmd == "stats"


def test_generate_parser_accepts_explicit_backfill_age_limit() -> None:
    parser = _build_parser()

    args, unknown = parser.parse_known_args(
        [
            "generate",
            "--date",
            "2026-09-06",
            "--backfill",
            "--max-age-hours",
            "168",
        ]
    )

    assert unknown == []
    assert args.max_age_hours == 168.0


def test_generate_parser_accepts_skip_existing_for_scheduled_retries() -> None:
    parser = _build_parser()

    args = parser.parse_args(
        ["generate", "--date", "2026-09-11", "--skip-existing"]
    )

    assert args.skip_existing is True


@pytest.mark.parametrize(
    ("backfill", "max_age_hours"),
    [(False, 72.0), (True, 0.0), (True, 169.0)],
)
def test_generate_rejects_unsafe_age_limit_before_side_effects(
    backfill: bool,
    max_age_hours: float,
) -> None:
    args = Namespace(
        date=__import__("datetime").date(2026, 9, 6),
        backfill=backfill,
        max_age_hours=max_age_hours,
        skip_existing=False,
    )

    with (
        patch("ai_brief.cli.connect") as connect,
        patch("ai_brief.cli.generate_for_review", new_callable=AsyncMock) as generate,
    ):
        generate.return_value = SimpleNamespace(
            brief_date="2026-09-06",
            status="awaiting_approval",
            run_id="test-run",
            exit_code=0,
        )
        result = __import__("asyncio").run(_cmd_generate(args))

    assert result == 2
    connect.assert_not_called()
    generate.assert_not_awaited()


def test_generate_passes_safe_age_limit_to_workflow() -> None:
    args = Namespace(
        date=__import__("datetime").date(2026, 9, 6),
        backfill=True,
        max_age_hours=168.0,
        skip_existing=False,
    )

    with (
        patch("ai_brief.cli.connect") as connect,
        patch("ai_brief.cli.GmailDigestAdapter") as adapter,
        patch("ai_brief.cli.generate_for_review", new_callable=AsyncMock) as generate,
    ):
        generate.return_value = SimpleNamespace(
            brief_date="2026-09-06",
            status="awaiting_approval",
            run_id="test-run",
            exit_code=0,
        )
        result = __import__("asyncio").run(_cmd_generate(args))

    assert result == 0
    adapter.assert_called_once_with(allow_fallback=False)
    assert generate.await_args is not None
    assert generate.await_args.kwargs == {
        "backfill": True,
        "max_digest_age_hours": 168.0,
        "preserve_existing": False,
    }
    connect.return_value.close.assert_called_once()


@pytest.mark.parametrize("status", ["awaiting_approval", "approved", "published"])
def test_generate_skip_existing_preserves_a_successful_daily_row(status: str) -> None:
    args = Namespace(
        date=__import__("datetime").date(2026, 9, 11),
        backfill=False,
        max_age_hours=None,
        skip_existing=True,
    )

    with (
        patch("ai_brief.cli.connect") as connect,
        patch("ai_brief.cli.storage.fetch_brief_status", return_value=status),
        patch("ai_brief.cli.generate_for_review", new_callable=AsyncMock) as generate,
    ):
        result = __import__("asyncio").run(_cmd_generate(args))

    assert result == 0
    generate.assert_not_awaited()
    connect.return_value.close.assert_called_once()


def test_generate_skip_existing_retries_a_blocked_daily_row() -> None:
    args = Namespace(
        date=__import__("datetime").date(2026, 9, 11),
        backfill=False,
        max_age_hours=None,
        skip_existing=True,
    )

    with (
        patch("ai_brief.cli.connect") as connect,
        patch("ai_brief.cli.storage.fetch_brief_status", return_value="blocked"),
        patch("ai_brief.cli.generate_for_review", new_callable=AsyncMock) as generate,
    ):
        generate.return_value = SimpleNamespace(
            brief_date="2026-09-11",
            status="awaiting_approval",
            run_id="test-run",
            exit_code=0,
        )
        result = __import__("asyncio").run(_cmd_generate(args))

    assert result == 0
    assert generate.await_args is not None
    assert generate.await_args.kwargs["preserve_existing"] is True
    connect.return_value.close.assert_called_once()


def test_legacy_daily_is_fail_closed() -> None:
    assert __import__("asyncio").run(_cmd_daily(Namespace())) == 2


def test_review_commands_do_not_import_send_pending() -> None:
    with patch("ai_brief.cli.deliverer.send_pending") as send_pending:
        parser = _build_parser()
        assert parser.parse_args(["generate", "--date", "2026-08-12"]).cmd == "generate"
        assert parser.parse_args(["approve", "--date", "2026-08-12"]).cmd == "approve"
        assert parser.parse_args(["preview-url", "--date", "2026-08-12"]).cmd == "preview-url"
        send_pending.assert_not_called()
