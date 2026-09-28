"""CLI workflow contract tests for Phase 3 Task 6."""

from argparse import Namespace
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from ai_brief import config, runner, storage
from ai_brief.cli import _build_parser, _cmd_daily, _cmd_generate
from ai_brief.digest import generate, uploader
from ai_brief.digest.generate import DigestBundle
from ai_brief.digest.imap_client import Attachment
from ai_brief.digest.input import DigestEnvelope, DigestKind
from ai_brief.schema import DigestSection, DigestStory, Theme


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


async def test_frozen_v4_workflow_publishes_two_complete_cases_and_blocks_incomplete_input(
) -> None:
    brief_date = date(2026, 9, 28)
    run_id = UUID("0f35ec9c-fc0e-4da9-91b4-0cb240d74a10")

    def section(theme: Theme, prefix: str, count: int) -> DigestSection:
        labels = ["海外新闻", "海外新闻", "海外新闻", "国内新闻", "国内新闻"]
        return DigestSection(
            theme=theme,
            header_image=None if theme is Theme.AGENT_TOOLS else "https://aivizens.com/header.jpg",
            stories=[
                DigestStory(
                    headline=f"{prefix} {index}",
                    summary="可验证的摘要。",
                    url=f"https://openai.com/{prefix.lower()}-{index}",
                    label=labels[index - 1] if theme is Theme.MODEL_RESEARCH else "",
                )
                for index in range(1, count + 1)
            ],
        )

    sections = {
        "events": section(Theme.MODEL_RESEARCH, "Today", 5),
        "builder": section(Theme.PRODUCT_TOOLS, "Masters", 3),
        "research": section(Theme.AI_RESEARCH, "Research", 1),
        "agent": section(Theme.AGENT_TOOLS, "Agents", 3),
    }

    def opc_html(*, include_second_insight: bool) -> str:
        second_insight = (
            "<p>案例启示：小团队以快速迭代建立优势。</p>"
            if include_second_insight
            else ""
        )
        return (
            "<h3>案例1 · Alice：Zipchat 恢复增长</h3>"
            "<p>案例背景：平台变化后收入归零。</p>"
            "<p>解决方案：重做电商 AI 销售代理。</p>"
            "<p>案例启示：聚焦可验证的客户价值。</p>"
            "<p>收入：$10K MRR</p>"
            '<p><a href="https://www.indiehackers.com/post/case-one">来源</a></p>'
            "<h3>案例2 · Bob：Tiny Studio 稳定获客</h3>"
            "<p>案例背景：独立工作室缺少稳定获客渠道。</p>"
            "<p>解决方案：围绕细分需求建立自动化交付。</p>"
            f"{second_insight}"
            "<p>收入：$2K MRR</p>"
            '<p><a href="https://www.indiehackers.com/post/case-two">来源</a></p>'
        )

    def digests(*, include_second_insight: bool) -> dict[DigestKind, DigestEnvelope | None]:
        received_at = datetime.now(UTC)
        result: dict[DigestKind, DigestEnvelope | None] = {}
        for kind, digest_section in sections.items():
            digest_kind = cast(DigestKind, kind)
            result[digest_kind] = DigestEnvelope(
                kind=digest_kind,
                message_id=f"<{kind}@test>",
                subject=f"{kind}-{brief_date}",
                received_at=received_at,
                requested_date=brief_date,
                matched_date=brief_date,
                used_fallback=False,
                text="\n".join(story.url for story in digest_section.stories),
                html=None,
                attachments=(),
            )
        result["engineering"] = None
        result["opc"] = DigestEnvelope(
            kind="opc",
            message_id="<opc@test>",
            subject=f"ai-opc-sharing {brief_date}",
            received_at=received_at,
            requested_date=brief_date,
            matched_date=brief_date,
            used_fallback=False,
            text=None,
            html=opc_html(include_second_insight=include_second_insight),
            attachments=(
                Attachment("case-1.png", "image/png", b"case-one"),
                Attachment("case-2.png", "image/png", b"case-two"),
            ),
        )
        return result

    async def run_case(
        *, include_second_insight: bool
    ) -> tuple[
        runner.GenerationResult,
        dict[str, object],
        list[dict[str, object]],
        runner.TransitionResult,
        runner.ReleaseResult,
    ]:
        state: dict[str, object] = {}
        deliveries: list[dict[str, object]] = []
        source_digests = digests(include_second_insight=include_second_insight)

        async def build_modules(
            requested_date: date,
            envelopes: dict[DigestKind, DigestEnvelope | None],
        ) -> DigestBundle:
            assert requested_date == brief_date
            opc_envelope = envelopes["opc"]
            assert opc_envelope is not None
            cases, candidate_count = generate.build_opc_cases(
                brief_date.isoformat(),
                opc_envelope,
                lambda: {
                    "USD": Decimal("1"),
                    "EUR": Decimal("1"),
                    "CNY": Decimal("7"),
                },
            )
            return DigestBundle(
                subject="双 OPC 案例进入日报",
                preheader="两条案例与今日 AI 更新",
                editorial="核心判断。",
                intro_bullets=[],
                today_ai=sections["events"],
                ai_masters=sections["builder"],
                ai_research=sections["research"],
                agent_tools=sections["agent"],
                opc_cases=cases,
                opc_candidate_count=candidate_count,
            )

        def save_generated_brief(_connection: object, **kwargs: object) -> None:
            state.update(kwargs)

        def lock_for_approval(_connection: object, _date: date) -> object:
            return SimpleNamespace(
                status=state["status"],
                quality_report=state["quality_report"],
            )

        def approve_locked(_connection: object, _date: date, **_kwargs: object) -> None:
            state["status"] = "approved"

        def lock_for_release(_connection: object, _date: date) -> object:
            return SimpleNamespace(
                status=state["status"],
                content=state["content"],
                source_run_id=run_id,
            )

        def insert_delivery(_connection: object, **kwargs: object) -> bool:
            deliveries.append(kwargs)
            return True

        def publish(_connection: object, _date: date, **_kwargs: object) -> None:
            state["published_content"] = state["content"]
            state["status"] = "published"

        connection = MagicMock()
        adapter = SimpleNamespace(fetch=lambda _date: source_digests)
        with (
            patch.object(config, "get_model", return_value="test-model"),
            patch.object(storage, "start_digest_run", return_value=run_id),
            patch.object(storage, "claim_brief_generation", return_value="started"),
            patch.object(storage, "fetch_previous_brief", return_value=None),
            patch.object(storage, "save_generated_brief", side_effect=save_generated_brief),
            patch.object(storage, "finish_digest_run"),
            patch.object(storage, "lock_brief_for_approval", side_effect=lock_for_approval),
            patch.object(storage, "approve_locked_brief", side_effect=approve_locked),
            patch.object(storage, "lock_brief_for_release", side_effect=lock_for_release),
            patch.object(
                storage,
                "fetch_active_subscribers",
                return_value=[
                    storage.ActiveSubscriber(
                        id="subscriber-1",
                        email="reader@example.net",
                        unsubscribe_token="unsubscribe-test-token",  # noqa: S106
                    )
                ],
            ),
            patch.object(storage, "insert_delivery_if_missing", side_effect=insert_delivery),
            patch.object(
                storage,
                "publish_locked_brief_and_complete_run",
                side_effect=publish,
            ),
            patch.object(runner, "build_digest_modules", side_effect=build_modules),
            patch.object(runner, "_alert"),
            patch.object(generate, "_is_usable_header_image", return_value=True),
            patch.object(
                generate,
                "_find_hero_band",
                side_effect=lambda data, _aspect: (data, "image/png"),
            ),
            patch.object(
                uploader,
                "upload_image",
                side_effect=[
                    "https://aivizens.com/opc-case-1.png",
                    "https://aivizens.com/opc-case-2.png",
                ],
            ),
        ):
            generated = await runner.generate_for_review(connection, brief_date, adapter)
            approval = runner.approve_brief(
                connection,
                brief_date,
                approved_by="test-operator",
            )
            released = runner.release_approved(connection, brief_date)

        return generated, state, deliveries, approval, released

    generated, state, deliveries, approval, released = await run_case(
        include_second_insight=True
    )
    assert generated.status == "awaiting_approval"
    assert approval.status == "approved"
    assert released.status == "published"
    published = state["published_content"]
    assert isinstance(published, dict)
    assert [case["headline"] for case in published["opc_cases"]] == [
        "Zipchat 恢复增长",
        "Tiny Studio 稳定获客",
    ]
    assert len(deliveries) == 1
    for rendered in (deliveries[0]["content_html"], deliveries[0]["content_text"]):
        assert isinstance(rendered, str)
        assert rendered.index("案例 1") < rendered.index("案例 2")
        assert rendered.count("案例背景：") == 2
        assert rendered.count("解决方案：") == 2
        assert rendered.count("案例启示：") == 2

    (
        blocked,
        blocked_state,
        blocked_deliveries,
        blocked_approval,
        blocked_release,
    ) = await run_case(include_second_insight=False)
    assert blocked.status == "blocked"
    assert blocked_approval.reason == "not_approvable"
    assert blocked_release.reason == "not_approved"
    assert "published_content" not in blocked_state
    assert blocked_deliveries == []
