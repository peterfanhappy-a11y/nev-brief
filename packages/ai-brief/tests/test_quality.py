"""Deterministic quality-gate tests; all fixtures are local and side-effect free."""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from ai_brief.digest.input import DigestEnvelope, DigestKind
from ai_brief.quality import QualityReport, validate_brief
from ai_brief.schema import (
    AiBriefContent,
    DigestSection,
    DigestStory,
    Stage1Stats,
    Theme,
)
from ai_brief.storage import _safe_quality_report

NOW = datetime(2026, 8, 4, 0, 0, tzinfo=UTC)
BRIEF_DATE = date(2026, 8, 4)


def _story(
    headline: str,
    url: str,
    *,
    summary: str = "A concise sourced summary.",
) -> DigestStory:
    return DigestStory(headline=headline, summary=summary, url=url, label="source")


def _section(
    theme: Theme,
    stories: list[DigestStory],
    *,
    image: bool = True,
) -> DigestSection:
    return DigestSection(
        theme=theme,
        header_image="https://aivizens.com/images/header.png" if image else None,
        header_image_alt="Header",
        stories=stories,
    )


def _valid_brief() -> AiBriefContent:
    return AiBriefContent(
        brief_date=BRIEF_DATE.isoformat(),
        subject="AI agents move from demos into production",
        preheader="Three research and engineering shifts worth tracking",
        editorial="Today’s evidence points to more reliable, useful AI systems.",
        intro_bullets=["Models improve", "Tools mature"],
        today_ai=_section(
            Theme.MODEL_RESEARCH,
            [
                _story("Today 1", "https://openai.com/news/one"),
                _story("Today 2", "https://openai.com/news/two"),
                _story("Today 3", "https://openai.com/news/three"),
            ],
        ),
        ai_masters=_section(
            Theme.PRODUCT_TOOLS,
            [
                _story("Master 1", "https://x.com/builder/status/1"),
                _story("Master 2", "https://x.com/builder/status/2"),
                _story("Master 3", "https://x.com/builder/status/3"),
            ],
        ),
        ai_research=_section(
            Theme.AI_RESEARCH,
            [_story("Research", "https://arxiv.org/abs/2608.00001")],
        ),
        ai_engineering=_section(
            Theme.AI_ENGINEERING,
            [
                _story("Engineering 1", ""),
                _story("Engineering 2", ""),
            ],
        ),
        agent_tools=_section(
            Theme.AGENT_TOOLS,
            [
                _story("Agent 1", "https://github.com/acme/agent-one"),
                _story("Agent 2", "https://github.com/acme/agent-two"),
            ],
            image=False,
        ),
        stage1_stats=Stage1Stats(candidates=11, dupe_groups=0),
    )


def _envelope(
    kind: DigestKind,
    *,
    age_hours: float = 2.0,
    used_fallback: bool = False,
    source_urls: tuple[str, ...] | None = None,
) -> DigestEnvelope:
    default_urls: dict[DigestKind, tuple[str, ...]] = {
        "events": (
            "https://openai.com/news/one",
            "https://openai.com/news/two",
            "https://openai.com/news/three",
        ),
        "builder": (
            "https://x.com/builder/status/1",
            "https://x.com/builder/status/2",
            "https://x.com/builder/status/3",
        ),
        "research": ("https://arxiv.org/abs/2608.00001",),
        "engineering": (),
        "agent": (
            "https://github.com/acme/agent-one",
            "https://github.com/acme/agent-two",
        ),
    }
    trusted_urls = source_urls if source_urls is not None else default_urls[kind]
    source_body = "\n".join(trusted_urls)
    return DigestEnvelope(
        kind=kind,
        message_id=f"<{kind}@gmail.test>",
        subject=f"{kind}-{BRIEF_DATE.isoformat()}",
        received_at=NOW - timedelta(hours=age_hours),
        requested_date=BRIEF_DATE,
        matched_date=BRIEF_DATE,
        used_fallback=used_fallback,
        text=source_body,
        html=f"<p>{source_body}</p>",
        attachments=(),
    )


def _valid_digests() -> dict[DigestKind, DigestEnvelope | None]:
    return {
        kind: _envelope(kind)
        for kind in ("events", "builder", "research", "engineering", "agent")
    }


def _report(
    brief: AiBriefContent | None = None,
    digests: dict[DigestKind, DigestEnvelope | None] | None = None,
    **kwargs: Any,
) -> QualityReport:
    return validate_brief(
        brief or _valid_brief(),
        digests or _valid_digests(),
        existing_status=kwargs.pop("existing_status", None),
        deepseek_complete=kwargs.pop("deepseek_complete", True),
        qwen_complete=kwargs.pop("qwen_complete", True),
        now=kwargs.pop("now", NOW),
        **kwargs,
    )


def _codes(report: QualityReport, kind: str = "blockers") -> list[str]:
    return [issue.code for issue in getattr(report, kind)]


def test_valid_brief_passes_with_complete_counts_and_freshness_metrics() -> None:
    """An empty/default result must not allow a candidate without operational evidence."""
    report = _report()

    assert report.passed is True
    assert report.blockers == ()
    assert report.warnings == ()
    assert report.metrics["today_ai_story_count"] == 3
    assert report.metrics["ai_masters_story_count"] == 3
    assert report.metrics["research_story_count"] == 1
    assert report.metrics["engineering_story_count"] == 2
    assert report.metrics["agent_story_count"] == 2
    assert report.metrics["tool_module_count"] == 3
    assert report.metrics["parsed_items"] == 11
    assert report.metrics["events_freshness_hours"] == 2.0
    assert report.metrics["max_digest_freshness_hours"] == 2.0
    assert report.metrics["quality_passed"] is True


@pytest.mark.parametrize(
    ("section_name", "code"),
    [
        ("today_ai", "today_ai_story_count_below_minimum"),
        ("ai_masters", "ai_masters_story_count_below_minimum"),
    ],
)
def test_fewer_than_three_primary_stories_blocks(
    section_name: str,
    code: str,
) -> None:
    """Lowering either primary-section minimum would publish an incomplete daily brief."""
    brief = _valid_brief()
    section = getattr(brief, section_name)
    assert section is not None
    setattr(brief, section_name, section.model_copy(update={"stories": section.stories[:2]}))

    report = _report(brief)

    assert code in _codes(report)
    assert report.passed is False


def test_fewer_than_two_available_tool_modules_blocks() -> None:
    """Treating one tool-learning module as sufficient would violate launch completeness."""
    brief = _valid_brief().model_copy(update={"ai_research": None, "ai_engineering": None})
    digests = _valid_digests()
    digests["research"] = None
    digests["engineering"] = None

    report = _report(brief, digests)

    assert "tool_module_count_below_minimum" in _codes(report)
    assert report.metrics["tool_module_count"] == 1
    assert report.metrics["missing_tool_module_count"] == 2
    assert report.passed is False


def test_schema_failure_is_reported_from_a_constructed_invalid_model() -> None:
    """Unchecked model_construct data must not bypass the gate via its annotation."""
    valid_payload = _valid_brief().model_dump(mode="python")
    valid_payload["version"] = "not-an-integer"
    brief = AiBriefContent.model_construct(**valid_payload)

    report = _report(brief)

    assert "schema_invalid" in _codes(report)
    assert report.metrics["schema_valid"] is False
    assert report.passed is False


@pytest.mark.parametrize("invalid_stories", ["broken", ["broken"]])
def test_schema_failure_in_nested_stories_returns_a_report(invalid_stories: object) -> None:
    """Malformed nested section data must fail closed without crashing validation."""
    brief = _valid_brief()
    brief.today_ai = DigestSection.model_construct(
        theme=Theme.MODEL_RESEARCH,
        stories=invalid_stories,
    )

    report = _report(brief)

    assert "schema_invalid" in _codes(report)
    assert report.metrics["schema_valid"] is False
    assert report.passed is False


@pytest.mark.parametrize(
    ("missing_field", "expected_code"),
    [("url", "critical_url_missing"), ("summary", "schema_invalid")],
)
def test_constructed_story_missing_fields_returns_a_report(
    missing_field: str,
    expected_code: str,
) -> None:
    """A constructed story with missing fields must not crash downstream validators."""
    brief = _valid_brief()
    assert brief.today_ai is not None
    invalid_story = DigestStory.model_construct(
        headline="Incomplete story",
        summary="Summary",
        url="https://openai.com/news/one",
    )
    object.__delattr__(invalid_story, missing_field)
    brief.today_ai.stories[0] = invalid_story

    report = _report(brief)

    assert expected_code in _codes(report)
    assert report.passed is False


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("subject", " \t", "subject_blank"),
        ("editorial", "\n", "editorial_blank"),
        ("intro_bullets", [" ", "\t"], "intro_blank"),
    ],
)
def test_blank_editorial_fields_block(field: str, value: object, code: str) -> None:
    """Whitespace-only editorial content must not pass Pydantic's structural checks."""
    brief = _valid_brief().model_copy(update={field: value})

    report = _report(brief)

    assert code in _codes(report)
    assert report.passed is False


@pytest.mark.parametrize(
    "path",
    [
        "today_ai.stories[0].url",
        "ai_masters.stories[0].url",
        "ai_research.stories[0].url",
        "agent_tools.stories[0].url",
    ],
)
def test_missing_critical_source_url_blocks_every_linked_digest_section(path: str) -> None:
    """Skipping a linked section would let model-authored text lose source traceability."""
    brief = _valid_brief()
    section_name = path.split(".", 1)[0]
    section = getattr(brief, section_name)
    assert section is not None
    section.stories[0].url = ""

    report = _report(brief)

    assert any(
        issue.code == "critical_url_missing" and issue.path == path
        for issue in report.blockers
    )


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("http://openai.com/news", "url_not_https"),
        ("ftp://openai.com/news", "url_not_https"),
        ("#source", "placeholder_url"),
        ("javascript:alert(1)", "placeholder_url"),
        ("https://example.com/story", "placeholder_url"),
        ("https://news.example.test/story", "placeholder_url"),
        ("https://example.invalid/story", "placeholder_url"),
        ("https://placeholder.invalid/story", "placeholder_url"),
        ("https://openai.com/TBD", "placeholder_url"),
        ("https://openai.com/TBD-v2", "placeholder_url"),
        ("https://openai.com/TODO", "placeholder_url"),
        ("https://openai.com/TODO.html", "placeholder_url"),
        ("https://openai.com/placeholder.json", "placeholder_url"),
    ],
)
def test_critical_url_rejects_non_https_and_placeholders(url: str, code: str) -> None:
    """A permissive URL branch would allow invented, inert, or unsafe source links."""
    brief = _valid_brief()
    assert brief.today_ai is not None
    brief.today_ai.stories[0].url = url

    report = _report(brief)

    assert any(
        issue.code == code and issue.path == "today_ai.stories[0].url"
        for issue in report.blockers
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://[",
        "https://openai.com:bad-port/story",
        "https://exa mple.com/story",
        "https://%zz/story",
    ],
)
def test_malformed_https_url_returns_a_stable_blocker(url: str) -> None:
    """Malformed HTTPS parsing must fail closed instead of raising or reaching provenance."""
    brief = _valid_brief()
    assert brief.today_ai is not None
    brief.today_ai.stories[0].url = url

    report = _report(brief)

    assert any(
        issue.code == "placeholder_url"
        and issue.path == "today_ai.stories[0].url"
        for issue in report.blockers
    )


def test_well_formed_but_invented_url_is_not_accepted_as_a_source() -> None:
    """Known-domain syntax alone must not let a model invent a source URL."""
    brief = _valid_brief()
    assert brief.today_ai is not None
    brief.today_ai.stories[0].url = "https://openai.com/news/invented"

    report = _report(brief)

    assert any(
        issue.code == "critical_url_missing"
        and issue.path == "today_ai.stories[0].url"
        for issue in report.blockers
    )


def test_placeholder_marker_inside_a_legitimate_token_is_not_blocked() -> None:
    """The TBD marker must not reject an unrelated Digest-provenanced identifier."""
    valid_url = "https://github.com/acme/notbd-tool"
    brief = _valid_brief()
    assert brief.agent_tools is not None
    brief.agent_tools.stories[0].url = valid_url
    digests = _valid_digests()
    digests["agent"] = _envelope(
        "agent",
        source_urls=(valid_url, "https://github.com/acme/agent-two"),
    )

    report = _report(brief, digests)

    assert "placeholder_url" not in _codes(report)
    assert report.passed is True


def test_todoist_source_is_an_unknown_domain_warning_not_a_placeholder() -> None:
    """The TODO token must not match inside a legitimate Digest-provenanced hostname."""
    valid_url = "https://todoist.com/inspiration/ai-workflows"
    brief = _valid_brief()
    assert brief.today_ai is not None
    brief.today_ai.stories[0].url = valid_url
    digests = _valid_digests()
    digests["events"] = _envelope(
        "events",
        source_urls=(
            valid_url,
            "https://openai.com/news/two",
            "https://openai.com/news/three",
        ),
    )

    report = _report(brief, digests)

    assert "placeholder_url" not in _codes(report)
    assert "source_domain_unknown" in _codes(report, "warnings")
    assert report.passed is True


def test_stale_required_digest_blocks_using_the_supplied_clock() -> None:
    """Using wall-clock time or ignoring the 24-hour boundary would make replay nondeterministic."""
    digests = _valid_digests()
    digests["events"] = _envelope("events", age_hours=24.01)

    report = _report(digests=digests)

    assert any(
        issue.code == "required_digest_stale"
        and issue.path == "digests.events.received_at"
        for issue in report.blockers
    )
    assert report.metrics["events_freshness_hours"] == pytest.approx(24.01)
    assert report.metrics["required_digests_fresh"] is False


def test_digest_received_far_in_the_future_blocks_using_the_supplied_clock() -> None:
    """Clamping every negative age to zero must not accept an impossible receipt time."""
    digests = _valid_digests()
    digests["events"] = _envelope("events", age_hours=-1.0)

    report = _report(digests=digests, now=NOW)

    assert any(
        issue.code == "required_digest_stale"
        and issue.path == "digests.events.received_at"
        for issue in report.blockers
    )
    assert report.metrics["events_freshness_hours"] == 0.0
    assert report.metrics["required_digests_fresh"] is False


def test_digest_at_five_minute_future_clock_skew_boundary_passes() -> None:
    """The documented five-minute tolerance must include its exact boundary."""
    digests = _valid_digests()
    digests["events"] = _envelope("events", age_hours=-(5 / 60))

    report = _report(digests=digests, now=NOW)

    assert "required_digest_stale" not in _codes(report)
    assert report.metrics["events_freshness_hours"] == 0.0
    assert report.metrics["required_digests_fresh"] is True


@pytest.mark.parametrize(
    ("kind", "boundary_hours"),
    [("events", 24.0), ("research", 40.0)],
)
def test_fractionally_stale_digest_cannot_pass_after_metric_rounding(
    kind: DigestKind,
    boundary_hours: float,
) -> None:
    """Persisted metric rounding must not weaken the raw freshness cutoff."""
    digests = _valid_digests()
    digests[kind] = _envelope(kind, age_hours=boundary_hours + 0.0004)

    report = _report(digests=digests)

    assert any(
        issue.code == "required_digest_stale"
        and issue.path == f"digests.{kind}.received_at"
        for issue in report.blockers
    )
    assert report.metrics[f"{kind}_freshness_hours"] == boundary_hours


def test_incomplete_deepseek_after_retry_blocks() -> None:
    """A partial model result must never advance merely because its schema is shaped correctly."""
    report = _report(deepseek_complete=False)

    assert "deepseek_incomplete" in _codes(report)
    assert report.metrics["deepseek_complete"] is False
    assert report.passed is False


@pytest.mark.parametrize("status", ["approved", "published"])
def test_existing_approved_or_published_brief_is_immutable(status: str) -> None:
    """Regeneration must not overwrite content after the human-approval boundary."""
    report = _report(existing_status=status)

    assert "brief_status_protected" in _codes(report)
    assert report.metrics["existing_brief_protected"] is True
    assert report.passed is False


def test_exactly_one_missing_tool_module_warns_but_passes() -> None:
    """Conflating the one-module fallback with the hard minimum would block an approved fallback."""
    brief = _valid_brief().model_copy(update={"agent_tools": None})
    digests = _valid_digests()
    digests["agent"] = None

    report = _report(brief, digests)

    assert _codes(report, "warnings") == ["tool_module_missing"]
    assert report.metrics["tool_module_count"] == 2
    assert report.metrics["missing_tool_module_count"] == 1
    assert report.passed is True


def test_qwen_no_image_fallback_warns_but_passes() -> None:
    """Losing image-selection completion must remain visible without blocking text publication."""
    report = _report(qwen_complete=False)

    assert "qwen_image_fallback" in _codes(report, "warnings")
    assert report.metrics["qwen_complete"] is False
    assert report.metrics["qwen_image_fallback"] is True
    assert report.passed is True


def test_recent_40_hour_digest_fallback_warns_but_passes() -> None:
    """Silently using a date fallback would hide degraded source-date matching."""
    digests = _valid_digests()
    digests["research"] = _envelope("research", age_hours=39.5, used_fallback=True)

    report = _report(digests=digests)

    assert any(
        issue.code == "digest_date_fallback"
        and issue.path == "digests.research.used_fallback"
        for issue in report.warnings
    )
    assert report.metrics["digest_date_fallback"] is True
    assert report.metrics["research_freshness_hours"] == 39.5
    assert report.passed is True


def test_filtered_non_core_item_count_warns_and_is_measured() -> None:
    """Discarded off-topic inputs must not disappear from quality evidence."""
    brief = _valid_brief()
    brief.stage1_stats = Stage1Stats(
        candidates=13,
        dupe_groups=0,
        filtered_non_core_items=2,
    )

    report = _report(brief)

    assert "non_core_items_filtered" in _codes(report, "warnings")
    assert report.metrics["filtered_non_core_item_count"] == 2
    assert report.passed is True


def test_summary_near_section_limit_warns_with_story_path() -> None:
    """Checking only the schema's broad 260-character cap would miss section-specific pressure."""
    brief = _valid_brief()
    assert brief.today_ai is not None
    brief.today_ai.stories[1].summary = "界" * 135

    report = _report(brief)

    assert any(
        issue.code == "summary_near_limit"
        and issue.path == "today_ai.stories[1].summary"
        for issue in report.warnings
    )
    assert report.metrics["summary_near_limit_count"] == 1


def test_unknown_source_domain_warns_without_rejecting_valid_https() -> None:
    """A newly observed domain must be reviewable without being mistaken for an unsafe URL."""
    brief = _valid_brief()
    assert brief.today_ai is not None
    brief.today_ai.stories[0].url = "https://emerging-ai.news/story"

    digests = _valid_digests()
    digests["events"] = _envelope(
        "events",
        source_urls=(
            "https://emerging-ai.news/story",
            "https://openai.com/news/two",
            "https://openai.com/news/three",
        ),
    )

    report = _report(brief, digests)

    assert any(
        issue.code == "source_domain_unknown"
        and issue.path == "today_ai.stories[0].url"
        for issue in report.warnings
    )
    assert "placeholder_url" not in _codes(report)
    assert report.metrics["unknown_source_domain_count"] == 1
    assert report.passed is True


def test_issues_are_stably_sorted_by_path_then_code() -> None:
    """Validator call order must not make persisted or displayed issue order drift."""
    brief = _valid_brief().model_copy(update={"subject": "", "editorial": ""})
    assert brief.today_ai is not None
    brief.today_ai.stories = brief.today_ai.stories[:2]
    brief.today_ai.stories[0].url = "#"

    first = _report(brief)
    second = _report(brief)

    blocker_keys = [(issue.path or "", issue.code) for issue in first.blockers]
    warning_keys = [(issue.path or "", issue.code) for issue in first.warnings]
    assert blocker_keys == sorted(blocker_keys)
    assert warning_keys == sorted(warning_keys)
    assert first == second


def test_only_explicit_now_changes_freshness_metrics() -> None:
    """Ambient wall-clock access would make identical replay inputs produce different evidence."""
    early = _report(now=NOW)
    later = _report(now=NOW + timedelta(hours=3))

    assert early.metrics["events_freshness_hours"] == 2.0
    assert later.metrics["events_freshness_hours"] == 5.0


def test_generated_report_survives_the_storage_fail_closed_catalog() -> None:
    """Catalog drift must not silently erase gate codes, structural paths, or metrics."""
    brief = _valid_brief().model_copy(update={"subject": "", "agent_tools": None})
    digests = _valid_digests()
    digests["agent"] = None
    assert brief.today_ai is not None
    brief.today_ai.stories[0].url = "https://emerging-ai.news/story"
    digests["events"] = _envelope(
        "events",
        source_urls=(
            "https://emerging-ai.news/story",
            "https://openai.com/news/two",
            "https://openai.com/news/three",
        ),
    )
    report = _report(brief, digests, qwen_complete=False)

    persisted = _safe_quality_report(asdict(report))

    assert persisted is not None
    assert persisted["passed"] == report.passed
    assert persisted["metrics"] == report.metrics
    assert persisted["blockers"] == [
        {"code": issue.code, "path": issue.path} for issue in report.blockers
    ]
    assert persisted["warnings"] == [
        {"code": issue.code, "path": issue.path} for issue in report.warnings
    ]
