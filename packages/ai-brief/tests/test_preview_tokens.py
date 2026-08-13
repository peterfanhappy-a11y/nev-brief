from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from ai_brief.preview_tokens import build_preview_url, generate_preview_signature

VECTOR = json.loads(
    (Path(__file__).parent / "fixtures" / "preview-token-vector.json").read_text(
        encoding="utf-8"
    )
)


def test_shared_vector_signs_exact_ascii_payload() -> None:
    assert generate_preview_signature(
        VECTOR["date"],
        VECTOR["expires"],
        secret=VECTOR["secret"],
        environment="production",
    ) == VECTOR["signature"]


def test_builds_exact_relative_preview_url() -> None:
    assert build_preview_url(
        VECTOR["date"],
        VECTOR["expires"],
        secret=VECTOR["secret"],
        now_seconds=VECTOR["now"],
        environment="production",
    ) == (
        f'/preview/{VECTOR["date"]}?expires={VECTOR["expires"]}'
        f'&signature={VECTOR["signature"]}'
    )


@pytest.mark.parametrize("brief_date", ["2026-8-04", "2026-02-29", "", "not-a-date"])
def test_rejects_malformed_or_impossible_dates(brief_date: str) -> None:
    with pytest.raises(ValueError, match="date"):
        generate_preview_signature(
            brief_date,
            VECTOR["expires"],
            secret=VECTOR["secret"],
            environment="production",
        )


@pytest.mark.parametrize("expires", [True, 0, -1, 1.5, "1785812100"])
def test_rejects_invalid_expiry_shape(expires: object) -> None:
    with pytest.raises(ValueError, match="expires"):
        generate_preview_signature(
            VECTOR["date"],
            cast(Any, expires),
            secret=VECTOR["secret"],
            environment="production",
        )


@pytest.mark.parametrize("now_seconds", [VECTOR["expires"], VECTOR["expires"] + 1])
def test_refuses_to_build_expired_urls(now_seconds: int) -> None:
    with pytest.raises(ValueError, match="future"):
        build_preview_url(
            VECTOR["date"],
            VECTOR["expires"],
            secret=VECTOR["secret"],
            now_seconds=now_seconds,
            environment="production",
        )


def test_refuses_to_build_url_with_more_than_fifteen_minutes_lifetime() -> None:
    with pytest.raises(ValueError, match="900"):
        build_preview_url(
            VECTOR["date"],
            VECTOR["expires"],
            secret=VECTOR["secret"],
            now_seconds=VECTOR["expires"] - 901,
            environment="production",
        )


def test_missing_secret_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PREVIEW_SIGNING_SECRET", raising=False)

    with pytest.raises(ValueError, match="PREVIEW_SIGNING_SECRET"):
        generate_preview_signature(
            VECTOR["date"], VECTOR["expires"], environment="production"
        )


def test_short_non_test_secret_fails_closed() -> None:
    with pytest.raises(ValueError, match="32"):
        generate_preview_signature(
            VECTOR["date"],
            VECTOR["expires"],
            secret=VECTOR["secret"][:12],
            environment="production",
        )


def test_short_test_secret_is_allowed_for_isolated_tests() -> None:
    signature = generate_preview_signature(
        "2026-08-04",
        1785812100,
        secret=VECTOR["secret"][:11],
        environment="test",
    )

    assert len(signature) == 64
    assert signature == signature.lower()
