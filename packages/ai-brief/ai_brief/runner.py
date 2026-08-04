"""Atomic generation, human approval, and release workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import UUID

import psycopg
from nev_shared.config import get_settings
from nev_shared.feishu import AlertLevel, send_alert
from nev_shared.logger import get_logger
from pydantic import ValidationError

from ai_brief import composer, config, storage
from ai_brief.digest.generate import DigestBundle, build_digest_modules
from ai_brief.digest.gmail_input import GmailDigestAdapter
from ai_brief.digest.input import DigestEnvelope, DigestInputAdapter, DigestKind
from ai_brief.quality import QualityReport, validate_brief
from ai_brief.schema import AiBriefContent, BriefStatus, DigestSection, YesterdayTop

log = get_logger("ai_brief.runner")

GenerationStatus = Literal["blocked", "awaiting_approval", "conflict", "failed"]


@dataclass(frozen=True)
class GenerationResult:
    brief_date: str
    status: GenerationStatus
    run_id: UUID
    modules: int = 0
    quality_report: QualityReport | None = None
    exit_code: int = 0


@dataclass(frozen=True)
class TransitionResult:
    brief_date: str
    status: BriefStatus | Literal["missing"]
    changed: bool
    reason: str | None
    exit_code: int


@dataclass(frozen=True)
class ReleaseResult:
    brief_date: str
    status: BriefStatus | Literal["missing"]
    released: bool
    composed: int
    reason: str | None
    exit_code: int


@dataclass
class DailyResult:
    """Compatibility result for the legacy ``daily`` command.

    Generation now stops at review; composed/sent/failed remain zero until the
    explicit release and later delivery commands run.
    """

    brief_date: str
    modules: int = 0
    composed: int = 0
    sent: int = 0
    failed: int = 0
    aborted_at: str | None = None
    steps: list[str] = field(default_factory=list)


def _alert(level: AlertLevel, title: str, body: str) -> None:
    try:
        send_alert(level=level, title=title, body=body)
    except Exception:  # noqa: BLE001 - alert failure must not hide workflow state
        log.warning("ai_runner.alert_failed", title=title)


def _yesterday_top(conn: psycopg.Connection, brief_date: date) -> YesterdayTop | None:
    prev = storage.fetch_previous_brief(conn, brief_date)
    if not prev:
        return None
    ta = prev.get("today_ai") or {}
    stories = ta.get("stories") or []
    if stories:
        first = stories[0]
        if first.get("headline") and first.get("url"):
            return YesterdayTop(headline=first["headline"], url=first["url"])
    featured = prev.get("featured") or []
    if featured and featured[0].get("headline") and featured[0].get("url"):
        return YesterdayTop(headline=featured[0]["headline"], url=featured[0]["url"])
    return None


def _module_count(bundle: DigestBundle) -> int:
    return sum(
        section is not None
        for section in (
            bundle.today_ai,
            bundle.ai_masters,
            bundle.ai_research,
            bundle.ai_engineering,
            bundle.agent_tools,
        )
    )


def _deepseek_complete(bundle: DigestBundle) -> bool:
    tool_count = sum(
        section is not None
        for section in (bundle.ai_research, bundle.ai_engineering, bundle.agent_tools)
    )
    return bundle.today_ai is not None and bundle.ai_masters is not None and tool_count >= 2


def _qwen_complete(bundle: DigestBundle) -> bool:
    qwen_sections: tuple[DigestSection | None, ...] = (
        bundle.today_ai,
        bundle.ai_masters,
        bundle.ai_research,
    )
    return all(section is None or bool(section.header_image) for section in qwen_sections)


def _digest_sources(
    digests: dict[DigestKind, DigestEnvelope | None],
    bundle: DigestBundle,
) -> dict[str, dict[str, Any] | None]:
    section_by_kind: dict[DigestKind, DigestSection | None] = {
        "events": bundle.today_ai,
        "builder": bundle.ai_masters,
        "research": bundle.ai_research,
        "engineering": bundle.ai_engineering,
        "agent": bundle.agent_tools,
    }
    result: dict[str, dict[str, Any] | None] = {}
    for kind, envelope in digests.items():
        if envelope is None:
            result[kind] = None
            continue
        metadata = envelope.metadata()
        section = section_by_kind[kind]
        metadata["parse_count"] = len(section.stories) if section is not None else 0
        result[kind] = metadata
    return result


def _digest_metadata_only(
    digests: dict[DigestKind, DigestEnvelope | None],
) -> dict[str, dict[str, Any] | None]:
    """Strip source bodies before an exceptional run reaches persistence."""
    return {
        kind: envelope.metadata() if envelope is not None else None
        for kind, envelope in digests.items()
    }


async def generate_for_review(
    conn: psycopg.Connection,
    brief_date: date,
    adapter: DigestInputAdapter,
) -> GenerationResult:
    """Generate a candidate and stop at blocked or mandatory human review."""
    date_str = brief_date.isoformat()
    run_id = storage.start_digest_run(conn, brief_date, type(adapter).__name__)
    conn.commit()  # Durable run identity always precedes the daily-row claim.

    stage = "state"
    digests: dict[DigestKind, DigestEnvelope | None] = {}
    try:
        claim = storage.claim_brief_generation(conn, brief_date)
        if claim == "conflict":
            storage.finish_digest_run(
                conn,
                run_id,
                status="failed",
                digest_sources={},
                quality_report=None,
                stage="state",
                error_summary="brief_generation_failed",
            )
            conn.commit()
            log.warning("ai_runner.brief_conflict", brief_date=date_str)
            return GenerationResult(date_str, "conflict", run_id, exit_code=1)
        conn.commit()  # Release the daily-row lock before source/model work.

        # A read transaction must not remain open across adapter/model calls.
        yesterday_top = _yesterday_top(conn, brief_date)
        conn.commit()

        stage = "fetch"
        digests = adapter.fetch(brief_date)
        stage = "build"
        bundle = await build_digest_modules(brief_date, digests)
        brief = _build_brief_without_lookup(brief_date, bundle, yesterday_top)

        stage = "quality"
        report = validate_brief(
            brief,
            digests,
            existing_status="generating",
            deepseek_complete=_deepseek_complete(bundle),
            qwen_complete=_qwen_complete(bundle),
            now=datetime.now(UTC),
        )
        status: Literal["blocked", "awaiting_approval"] = (
            "awaiting_approval" if report.passed else "blocked"
        )
        sources = _digest_sources(digests, bundle)
        report_payload = asdict(report)

        stage = "storage"
        storage.save_generated_brief(
            conn,
            brief_date=brief_date,
            content=brief.model_dump(mode="json"),
            model=brief.model,
            digest_sources=sources,
            quality_report=report_payload,
            source_run_id=run_id,
            status=status,
        )
        storage.finish_digest_run(
            conn,
            run_id,
            status=status,
            digest_sources=sources,
            quality_report=report_payload,
            stage="quality" if status == "blocked" else None,
            error_summary="quality_gate_failed" if status == "blocked" else None,
        )
        conn.commit()

        modules = _module_count(bundle)
        if status == "blocked":
            codes = ",".join(issue.code for issue in report.blockers)
            _alert(AlertLevel.P1, "AI 简报质量阻断", f"{date_str} blockers={codes}")
        return GenerationResult(
            date_str,
            status,
            run_id,
            modules=modules,
            quality_report=report,
            exit_code=0 if report.passed else 1,
        )
    except Exception:  # noqa: BLE001 - convert pipeline faults into durable safe state
        conn.rollback()
        try:
            storage.mark_brief_generation_failed(conn, brief_date)
            storage.finish_digest_run(
                conn,
                run_id,
                status="failed",
                digest_sources=_digest_metadata_only(digests),
                quality_report=None,
                stage=stage,
                error_summary="brief_generation_failed",
            )
            conn.commit()
        except Exception:  # noqa: BLE001 - preserve rollback if failure recording fails
            conn.rollback()
            raise
        _alert(AlertLevel.P1, "AI 简报生成失败", f"{date_str} stage={stage}")
        return GenerationResult(date_str, "failed", run_id, exit_code=1)


def _build_brief_without_lookup(
    brief_date: date,
    bundle: DigestBundle,
    yesterday_top: YesterdayTop | None,
) -> AiBriefContent:
    intro = bundle.intro_bullets or (
        [story.headline for story in bundle.today_ai.stories]
        if bundle.today_ai is not None
        else []
    )
    subject = bundle.subject or (
        bundle.today_ai.stories[0].headline
        if bundle.today_ai is not None and bundle.today_ai.stories
        else ""
    )
    payload: dict[str, Any] = {
        "brief_date": brief_date.isoformat(),
        "subject": subject[:44],
        "preheader": bundle.preheader[:60],
        "editorial": bundle.editorial[:220],
        "intro_bullets": intro[:4],
        "today_ai": bundle.today_ai,
        "ai_masters": bundle.ai_masters,
        "ai_research": bundle.ai_research,
        "ai_engineering": bundle.ai_engineering,
        "agent_tools": bundle.agent_tools,
        "featured": [],
        "yesterday_top": yesterday_top,
        "model": config.get_model(),
    }
    try:
        return AiBriefContent.model_validate(payload)
    except ValidationError:
        # Invalid model output belongs at the quality boundary, where it becomes
        # a reviewable ``blocked`` candidate instead of an opaque pipeline fault.
        return AiBriefContent.model_construct(**payload)


def approve_brief(
    conn: psycopg.Connection,
    brief_date: date,
    *,
    approved_by: str,
) -> TransitionResult:
    """Apply the mandatory human approval transition without publishing or sending."""
    operator = approved_by.strip()
    if not operator:
        raise ValueError("approved_by must be a non-empty local operator identifier")
    try:
        locked = storage.lock_brief_for_approval(conn, brief_date)
        if locked is None:
            conn.rollback()
            return TransitionResult(brief_date.isoformat(), "missing", False, "missing", 1)
        report = locked.quality_report
        if locked.status != "awaiting_approval" or not (
            isinstance(report, dict) and report.get("passed") is True
        ):
            conn.rollback()
            return TransitionResult(
                brief_date.isoformat(), locked.status, False, "not_approvable", 1
            )
        storage.approve_locked_brief(
            conn,
            brief_date,
            approved_by=operator,
        )
        conn.commit()
        return TransitionResult(brief_date.isoformat(), "approved", True, None, 0)
    except Exception:
        conn.rollback()
        raise


def release_approved(
    conn: psycopg.Connection,
    brief_date: date,
    *,
    only_email: str | None = None,
) -> ReleaseResult:
    """Publish frozen approved content and create missing deliveries atomically."""
    date_str = brief_date.isoformat()
    try:
        locked = storage.lock_brief_for_release(conn, brief_date)
        if locked is None:
            conn.rollback()
            _alert(AlertLevel.P1, "AI 简报未发布", f"{date_str} reason=missing")
            return ReleaseResult(date_str, "missing", False, 0, "not_approved", 1)
        if locked.status == "published":
            conn.rollback()
            return ReleaseResult(date_str, "published", False, 0, "already_published", 0)
        if locked.status != "approved":
            conn.rollback()
            _alert(
                AlertLevel.P1,
                "AI 简报未发布",
                f"{date_str} reason=not_approved status={locked.status}",
            )
            return ReleaseResult(date_str, locked.status, False, 0, "not_approved", 1)

        composed = composer.compose_frozen_brief(
            conn,
            brief_date,
            locked.content,
            only_email=only_email,
        ).get("composed", 0)
        storage.publish_locked_brief_and_complete_run(
            conn,
            brief_date,
            source_run_id=locked.source_run_id,
        )
        conn.commit()
        return ReleaseResult(date_str, "published", True, composed, None, 0)
    except Exception:
        conn.rollback()
        _alert(AlertLevel.P1, "AI 简报发布失败", f"{date_str} transaction_rolled_back=true")
        raise


async def run_daily(
    conn: psycopg.Connection,
    brief_date: date,
    *,
    only_email: str | None = None,
    dry_run: bool = False,
    skip_crawl: bool = False,
) -> DailyResult:
    """Compatibility wrapper: daily now generates for review and never sends."""
    del only_email, dry_run, skip_crawl
    generated = await generate_for_review(conn, brief_date, GmailDigestAdapter())
    result = DailyResult(brief_date=brief_date.isoformat(), modules=generated.modules)
    result.steps.append("generate")
    if generated.exit_code:
        result.aborted_at = generated.status
    return result


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url)
