"""CLI workflow contract tests for Phase 3 Task 6."""

from argparse import Namespace
from unittest.mock import patch

from ai_brief.cli import _build_parser, _cmd_daily


def test_cli_parser_exposes_review_workflow_commands() -> None:
    parser = _build_parser()
    assert parser.parse_args(["generate", "--date", "2026-08-12"]).cmd == "generate"
    assert parser.parse_args(["preview-url", "--date", "2026-08-12"]).cmd == "preview-url"
    assert parser.parse_args(["approve", "--date", "2026-08-12"]).cmd == "approve"
    assert parser.parse_args(["release", "--date", "2026-08-12"]).cmd == "release"
    assert parser.parse_args(["stats", "--json"]).cmd == "stats"


def test_legacy_daily_is_fail_closed() -> None:
    assert __import__("asyncio").run(_cmd_daily(Namespace())) == 2


def test_review_commands_do_not_import_send_pending() -> None:
    with patch("ai_brief.cli.deliverer.send_pending") as send_pending:
        parser = _build_parser()
        assert parser.parse_args(["generate", "--date", "2026-08-12"]).cmd == "generate"
        assert parser.parse_args(["approve", "--date", "2026-08-12"]).cmd == "approve"
        assert parser.parse_args(["preview-url", "--date", "2026-08-12"]).cmd == "preview-url"
        send_pending.assert_not_called()
