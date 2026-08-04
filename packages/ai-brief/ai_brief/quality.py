"""Pure, deterministic validation boundary for generated daily briefs."""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urlsplit

from pydantic import ValidationError

from ai_brief.digest.input import DigestEnvelope, DigestKind
from ai_brief.schema import (
    QUALITY_ISSUE_CODES,
    QUALITY_METRIC_KEYS,
    AiBriefContent,
    BriefStatus,
    DigestSection,
    DigestStory,
    quality_path_is_allowed,
)

_PRIMARY_STORY_MINIMUM = 3
_TOOL_MODULE_MINIMUM = 2
_PRIMARY_DIGEST_MAX_AGE_HOURS = 24.0
_TOOL_DIGEST_MAX_AGE_HOURS = 40.0
_SUMMARY_NEAR_LIMIT_RATIO = 0.9

_SECTION_SUMMARY_LIMITS = {
    "today_ai": 150,
    "ai_masters": 120,
    "ai_research": 200,
    "ai_engineering": 150,
    "agent_tools": 150,
}
_TOOL_SECTIONS = ("ai_research", "ai_engineering", "agent_tools")
_CRITICAL_URL_SECTIONS = ("today_ai", "ai_masters", "ai_research", "agent_tools")
_SECTION_DIGEST_KINDS: dict[str, DigestKind] = {
    "today_ai": "events",
    "ai_masters": "builder",
    "ai_research": "research",
    "ai_engineering": "engineering",
    "agent_tools": "agent",
}
_FRESHNESS_METRIC_KEYS: dict[DigestKind, str] = {
    "events": "events_freshness_hours",
    "builder": "builder_freshness_hours",
    "research": "research_freshness_hours",
    "engineering": "engineering_freshness_hours",
    "agent": "agent_freshness_hours",
}
_KNOWN_SOURCE_DOMAINS = frozenset(
    {
        "36kr.com",
        "anthropic.com",
        "arxiv.org",
        "deepmind.google",
        "github.com",
        "huggingface.co",
        "huxiu.com",
        "infoq.cn",
        "jiqizhixin.com",
        "openai.com",
        "qbitai.com",
        "rsshub.app",
        "techcrunch.com",
        "technologyreview.com",
        "theverge.com",
        "twitter.com",
        "venturebeat.com",
        "x.com",
    }
)
_PLACEHOLDER_DOMAINS = frozenset(
    {
        "127.0.0.1",
        "example.com",
        "example.net",
        "example.org",
        "example.test",
        "invalid",
        "localhost",
        "placeholder.invalid",
        "test",
    }
)
_PLACEHOLDER_PHRASES = (
    "change-me",
    "changeme",
    "example.test",
    "javascript:",
    "placeholder",
    "replace-me",
    "todo",
    "your-domain",
)
_PLACEHOLDER_TOKEN = re.compile(r"(?:^|[/?:#&=_.-])tbd(?:$|[/?:#&=_.-])", re.IGNORECASE)
_SOURCE_URL = re.compile(r"https://[^\s<>\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class QualityIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    blockers: tuple[QualityIssue, ...]
    warnings: tuple[QualityIssue, ...]
    metrics: dict[str, int | float | str | bool]


def _issue(code: str, message: str, path: str | None = None) -> QualityIssue:
    if code not in QUALITY_ISSUE_CODES:
        raise ValueError(f"quality issue code is outside the persistence catalog: {code}")
    if path is not None and not quality_path_is_allowed(path):
        raise ValueError(f"quality issue path is outside the persistence catalog: {path}")
    return QualityIssue(code=code, message=message, path=path)


def _sorted_issues(issues: list[QualityIssue]) -> tuple[QualityIssue, ...]:
    return tuple(sorted(issues, key=lambda issue: (issue.path or "", issue.code)))


def _section(brief: AiBriefContent, name: str) -> DigestSection | None:
    value = getattr(brief, name, None)
    return value if isinstance(value, DigestSection) else None


def _story_count(section: DigestSection | None) -> int:
    return len(_story_items(section))


def _story_items(section: DigestSection | None) -> tuple[tuple[int, DigestStory], ...]:
    stories = getattr(section, "stories", None)
    if not isinstance(stories, list):
        return ()
    return tuple(
        (index, story)
        for index, story in enumerate(stories)
        if isinstance(story, DigestStory)
    )


def _schema_is_valid(brief: AiBriefContent) -> bool:
    try:
        payload = brief.model_dump(mode="python", warnings=False)
        AiBriefContent.model_validate(payload)
    except (AttributeError, TypeError, ValueError, ValidationError):
        return False
    return True


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _raw_freshness_hours(envelope: DigestEnvelope, now: datetime) -> float:
    age = (_as_utc(now) - _as_utc(envelope.received_at)).total_seconds() / 3600
    return max(0.0, age)


def _freshness_hours(envelope: DigestEnvelope, now: datetime) -> float:
    return round(_raw_freshness_hours(envelope, now), 3)


def _host_is_known(host: str) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in _KNOWN_SOURCE_DOMAINS)


def _host_is_placeholder(host: str) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in _PLACEHOLDER_DOMAINS)


def _url_problem(url: str) -> tuple[str | None, str | None]:
    candidate = url.strip()
    if not candidate:
        return "critical_url_missing", None

    lowered = candidate.lower()
    if (
        candidate.startswith("#")
        or any(phrase in lowered for phrase in _PLACEHOLDER_PHRASES)
        or _PLACEHOLDER_TOKEN.search(lowered)
    ):
        return "placeholder_url", None

    parsed = urlsplit(candidate)
    if parsed.scheme.lower() != "https":
        return "url_not_https", None
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or _host_is_placeholder(host):
        return "placeholder_url", None
    return None, host


def _source_urls(envelope: DigestEnvelope | None) -> frozenset[str]:
    if envelope is None:
        return frozenset()
    source_text = unescape("\n".join(value or "" for value in (envelope.text, envelope.html)))
    return frozenset(
        match.group(0).rstrip(".,;:!?)]}〉》")
        for match in _SOURCE_URL.finditer(source_text)
    )


def _validate_urls(
    brief: AiBriefContent,
    digests: Mapping[DigestKind, DigestEnvelope | None],
    blockers: list[QualityIssue],
    warnings: list[QualityIssue],
) -> int:
    unknown_domain_count = 0
    for section_name in _CRITICAL_URL_SECTIONS:
        section = _section(brief, section_name)
        if section is None:
            continue
        trusted_urls = _source_urls(digests.get(_SECTION_DIGEST_KINDS[section_name]))
        for index, story in _story_items(section):
            path = f"{section_name}.stories[{index}].url"
            story_url = getattr(story, "url", "")
            raw_url = story_url if isinstance(story_url, str) else ""
            problem, host = _url_problem(raw_url)
            if problem == "critical_url_missing":
                blockers.append(_issue(problem, "Critical source URL is missing.", path))
            elif problem == "placeholder_url":
                blockers.append(_issue(problem, "Source URL is a placeholder.", path))
            elif problem == "url_not_https":
                blockers.append(_issue(problem, "Source URL must use HTTPS.", path))
            elif raw_url.strip() not in trusted_urls:
                blockers.append(
                    _issue(
                        "critical_url_missing",
                        "Critical source URL is absent from its trusted Digest.",
                        path,
                    )
                )
            elif host is not None and not _host_is_known(host):
                warnings.append(
                    _issue(
                        "source_domain_unknown",
                        "Source URL uses a domain outside the reviewed set.",
                        path,
                    )
                )
                unknown_domain_count += 1
    return unknown_domain_count


def _validate_summaries(brief: AiBriefContent, warnings: list[QualityIssue]) -> int:
    near_limit_count = 0
    for section_name, limit in _SECTION_SUMMARY_LIMITS.items():
        section = _section(brief, section_name)
        if section is None:
            continue
        threshold = math.ceil(limit * _SUMMARY_NEAR_LIMIT_RATIO)
        for index, story in _story_items(section):
            story_summary = getattr(story, "summary", "")
            summary = story_summary if isinstance(story_summary, str) else ""
            if len(summary) >= threshold:
                warnings.append(
                    _issue(
                        "summary_near_limit",
                        "Summary is near its section-specific character limit.",
                        f"{section_name}.stories[{index}].summary",
                    )
                )
                near_limit_count += 1
    return near_limit_count


def _validate_digests(
    brief: AiBriefContent,
    digests: Mapping[DigestKind, DigestEnvelope | None],
    now: datetime,
    blockers: list[QualityIssue],
    warnings: list[QualityIssue],
    metrics: dict[str, int | float | str | bool],
) -> tuple[bool, bool]:
    freshness_values: list[float] = []
    fallback_used = False
    required_fresh = True

    for kind, metric_key in _FRESHNESS_METRIC_KEYS.items():
        envelope = digests.get(kind)
        if envelope is None:
            continue
        freshness = _freshness_hours(envelope, now)
        metrics[metric_key] = freshness
        freshness_values.append(freshness)
        if envelope.used_fallback:
            fallback_used = True
            warnings.append(
                _issue(
                    "digest_date_fallback",
                    "Digest used the recent 40-hour date fallback.",
                    f"digests.{kind}.used_fallback",
                )
            )

    required_sections = ("today_ai", "ai_masters") + tuple(
        section_name
        for section_name in _TOOL_SECTIONS
        if _story_count(_section(brief, section_name)) > 0
    )
    for section_name in required_sections:
        kind = _SECTION_DIGEST_KINDS[section_name]
        envelope = digests.get(kind)
        limit = (
            _PRIMARY_DIGEST_MAX_AGE_HOURS
            if kind in {"events", "builder"}
            else _TOOL_DIGEST_MAX_AGE_HOURS
        )
        if envelope is None:
            required_fresh = False
            blockers.append(
                _issue(
                    "required_digest_stale",
                    "Required Digest is missing or stale.",
                    f"digests.{kind}",
                )
            )
            continue
        if _raw_freshness_hours(envelope, now) > limit:
            required_fresh = False
            blockers.append(
                _issue(
                    "required_digest_stale",
                    "Required Digest is missing or stale.",
                    f"digests.{kind}.received_at",
                )
            )

    metrics["max_digest_freshness_hours"] = max(freshness_values, default=0.0)
    return required_fresh, fallback_used


def validate_brief(
    brief: AiBriefContent,
    digests: Mapping[DigestKind, DigestEnvelope | None],
    *,
    existing_status: BriefStatus | None,
    deepseek_complete: bool,
    qwen_complete: bool,
    now: datetime,
) -> QualityReport:
    """Validate a generated brief without I/O or ambient clock access."""
    blockers: list[QualityIssue] = []
    warnings: list[QualityIssue] = []

    schema_valid = _schema_is_valid(brief)
    if not schema_valid:
        blockers.append(_issue("schema_invalid", "Brief content failed schema validation."))

    today_count = _story_count(_section(brief, "today_ai"))
    masters_count = _story_count(_section(brief, "ai_masters"))
    research_count = _story_count(_section(brief, "ai_research"))
    engineering_count = _story_count(_section(brief, "ai_engineering"))
    agent_count = _story_count(_section(brief, "agent_tools"))
    tool_counts = (research_count, engineering_count, agent_count)
    tool_module_count = sum(count > 0 for count in tool_counts)
    missing_tool_count = len(_TOOL_SECTIONS) - tool_module_count

    if today_count < _PRIMARY_STORY_MINIMUM:
        blockers.append(
            _issue(
                "today_ai_story_count_below_minimum",
                "Today AI requires at least three stories.",
                "today_ai",
            )
        )
    if masters_count < _PRIMARY_STORY_MINIMUM:
        blockers.append(
            _issue(
                "ai_masters_story_count_below_minimum",
                "AI Masters requires at least three stories.",
                "ai_masters",
            )
        )
    if tool_module_count < _TOOL_MODULE_MINIMUM:
        blockers.append(
            _issue(
                "tool_module_count_below_minimum",
                "At least two tool-learning modules must be usable.",
            )
        )
    elif missing_tool_count == 1:
        missing_section = next(
            section_name
            for section_name in _TOOL_SECTIONS
            if _story_count(_section(brief, section_name)) == 0
        )
        warnings.append(
            _issue(
                "tool_module_missing",
                "Exactly one tool-learning module is unavailable.",
                missing_section,
            )
        )

    subject = brief.subject if isinstance(getattr(brief, "subject", None), str) else ""
    editorial = brief.editorial if isinstance(getattr(brief, "editorial", None), str) else ""
    intro = brief.intro_bullets if isinstance(getattr(brief, "intro_bullets", None), list) else []
    if not subject.strip():
        blockers.append(_issue("subject_blank", "Subject must not be blank.", "subject"))
    if not editorial.strip():
        blockers.append(_issue("editorial_blank", "Editorial must not be blank.", "editorial"))
    if not intro or not any(isinstance(item, str) and item.strip() for item in intro):
        blockers.append(_issue("intro_blank", "Intro bullets must not be blank.", "intro_bullets"))

    unknown_domain_count = _validate_urls(brief, digests, blockers, warnings)
    summary_near_limit_count = _validate_summaries(brief, warnings)

    stage1_stats = getattr(brief, "stage1_stats", None)
    raw_filtered_count = getattr(stage1_stats, "filtered_non_core_items", 0)
    filtered_count = (
        raw_filtered_count
        if isinstance(raw_filtered_count, int)
        and not isinstance(raw_filtered_count, bool)
        and raw_filtered_count >= 0
        else 0
    )
    if filtered_count:
        warnings.append(
            _issue(
                "non_core_items_filtered",
                "Non-core source items were filtered before generation.",
            )
        )

    if not deepseek_complete:
        blockers.append(
            _issue("deepseek_incomplete", "DeepSeek output remained incomplete after retry.")
        )
    if not qwen_complete:
        warnings.append(
            _issue("qwen_image_fallback", "Qwen image selection used the no-image fallback.")
        )

    existing_protected = existing_status in {"approved", "published"}
    if existing_protected:
        blockers.append(
            _issue(
                "brief_status_protected",
                "Approved or published brief content is immutable.",
            )
        )

    metrics: dict[str, int | float | str | bool] = {
        "agent_story_count": agent_count,
        "ai_masters_story_count": masters_count,
        "deepseek_complete": deepseek_complete,
        "editorial_length": len(editorial),
        "engineering_story_count": engineering_count,
        "existing_brief_protected": existing_protected,
        "filtered_non_core_item_count": filtered_count,
        "intro_bullet_count": len(intro),
        "missing_tool_module_count": missing_tool_count,
        "parsed_items": today_count
        + masters_count
        + research_count
        + engineering_count
        + agent_count,
        "qwen_complete": qwen_complete,
        "qwen_image_fallback": not qwen_complete,
        "research_story_count": research_count,
        "schema_valid": schema_valid,
        "subject_length": len(subject),
        "summary_near_limit_count": summary_near_limit_count,
        "today_ai_story_count": today_count,
        "tool_module_count": tool_module_count,
        "unknown_source_domain_count": unknown_domain_count,
    }
    required_fresh, fallback_used = _validate_digests(
        brief,
        digests,
        now,
        blockers,
        warnings,
        metrics,
    )
    metrics["digest_date_fallback"] = fallback_used
    metrics["required_digests_fresh"] = required_fresh

    sorted_blockers = _sorted_issues(blockers)
    sorted_warnings = _sorted_issues(warnings)
    passed = not sorted_blockers
    metrics["blocker_count"] = len(sorted_blockers)
    metrics["quality_passed"] = passed
    metrics["warning_count"] = len(sorted_warnings)

    unknown_metric_keys = set(metrics) - QUALITY_METRIC_KEYS
    if unknown_metric_keys:
        unknown = ", ".join(sorted(unknown_metric_keys))
        raise ValueError(f"quality metrics are outside the persistence catalog: {unknown}")
    return QualityReport(
        passed=passed,
        blockers=sorted_blockers,
        warnings=sorted_warnings,
        metrics=metrics,
    )
