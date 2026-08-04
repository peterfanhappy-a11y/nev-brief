"""Runner safety boundaries for publication-state conflicts."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from ai_brief import composer, deliverer, runner, storage


async def test_run_daily_stops_before_compose_and_delivery_on_brief_conflict() -> None:
    connection = MagicMock()
    brief_date = date(2026, 8, 4)
    digests = {
        "events": None,
        "builder": None,
        "research": None,
        "engineering": None,
        "agent": None,
    }
    adapter = MagicMock()
    adapter.fetch.return_value = digests
    today_ai = SimpleNamespace(stories=[SimpleNamespace(headline="Test headline")])
    bundle = SimpleNamespace(
        today_ai=today_ai,
        ai_masters=None,
        ai_research=None,
        ai_engineering=None,
        agent_tools=None,
        intro_bullets=["Test headline"],
        subject="Test subject",
        preheader="Test preheader",
        editorial="Test editorial",
    )
    brief = MagicMock()
    brief.subject = "Test subject"
    brief.model = "test-model"
    brief.model_dump.return_value = {"subject": "Test subject"}

    digest_builder = AsyncMock(return_value=bundle)
    with (
        patch.object(runner, "GmailDigestAdapter", return_value=adapter),
        patch.object(runner, "build_digest_modules", digest_builder),
        patch.object(runner, "AiBriefContent", return_value=brief),
        patch.object(runner, "_yesterday_top", return_value=None),
        patch.object(runner, "_alert"),
        patch.object(storage, "upsert_daily_brief", return_value="conflict"),
        patch.object(composer, "compose_for_date") as compose,
        patch.object(
            deliverer,
            "send_pending",
            return_value=SimpleNamespace(sent=0, failed=0),
        ) as deliver,
    ):
        result = await runner.run_daily(connection, brief_date)

    assert result.aborted_at == "brief_conflict"
    assert result.steps == ["digest"]
    adapter.fetch.assert_called_once_with(brief_date)
    digest_builder.assert_awaited_once_with(brief_date, digests)
    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
    compose.assert_not_called()
    deliver.assert_not_called()
