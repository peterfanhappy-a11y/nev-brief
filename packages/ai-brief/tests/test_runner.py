"""Runner safety boundaries for publication-state conflicts."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from ai_brief import composer, deliverer, runner


async def test_run_daily_is_generation_only_and_never_composes_or_delivers() -> None:
    connection = MagicMock()
    brief_date = date(2026, 8, 4)
    adapter = MagicMock()
    generated = runner.GenerationResult(
        brief_date="2026-08-04",
        status="awaiting_approval",
        run_id=UUID("aee85a2c-9c58-4be9-8a30-d4aed5fa4690"),
        modules=5,
    )
    generate = AsyncMock(return_value=generated)
    with (
        patch.object(runner, "GmailDigestAdapter", return_value=adapter),
        patch.object(runner, "generate_for_review", generate),
        patch.object(composer, "compose_for_date") as compose,
        patch.object(deliverer, "send_pending") as deliver,
    ):
        result = await runner.run_daily(connection, brief_date)

    assert result.aborted_at is None
    assert result.steps == ["generate"]
    assert result.modules == 5
    generate.assert_awaited_once_with(connection, brief_date, adapter)
    compose.assert_not_called()
    deliver.assert_not_called()
