"""DeepSeek client (T7) — OpenAI-compatible SDK wrapper with retry + JSON parse fallback.

DeepSeek exposes an OpenAI-compatible /chat/completions endpoint, so we reuse the
official openai Python SDK (which uses httpx under the hood — hence respx for tests).

Failure path returns None so callers (e.g. entity_extractor) can fall back to dict-based
extraction. Acceptance gate 4: "DeepSeek JSON 解析失败时 fallback 到 entity_dict.yaml 命中".
"""
from __future__ import annotations

import json
import logging
from typing import Any, cast

import httpx
from nev_shared.config import get_settings
from nev_shared.logger import get_logger
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class _RetryableResponseError(Exception):
    """DeepSeek returned a successful HTTP response with unusable JSON content."""


# Retry transient transport errors and unusable model responses. Auth / bad-request /
# quota errors still fail fast (no point waiting when the request itself is invalid).
_RETRYABLE = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
    _RetryableResponseError,
)

log = get_logger("deepseek")

# Silence noisy openai SDK INFO logs (request/response dumps).
_OPENAI_LOG = logging.getLogger("openai")
_OPENAI_LOG.setLevel(logging.WARNING)
_HTTPX_LOG = logging.getLogger("httpx")
_HTTPX_LOG.setLevel(logging.WARNING)


def _client() -> AsyncOpenAI:
    s = get_settings()
    # Inject a httpx client with trust_env=False so the openai SDK does not
    # pick up HTTP_PROXY/HTTPS_PROXY/ALL_PROXY from the shell environment.
    return AsyncOpenAI(
        api_key=s.deepseek_api_key,
        base_url=s.deepseek_base_url,
        max_retries=0,
        http_client=httpx.AsyncClient(trust_env=False),
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
async def _call(
    system: str,
    user: str,
    model: str,
    max_tokens: int,
    temperature: float,
    thinking: bool | None,
) -> dict[str, Any]:
    extra_body: dict[str, Any] | None = None
    if thinking is not None:
        extra_body = {
            "thinking": {"type": "enabled" if thinking else "disabled"}
        }
    resp = await _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
        temperature=temperature,
        extra_body=extra_body,
    )
    choice = resp.choices[0]
    raw = choice.message.content or ""
    if choice.finish_reason != "stop":
        log.warning(
            "deepseek_response_incomplete",
            finish_reason=choice.finish_reason,
            raw_preview=raw[:200],
        )
        raise _RetryableResponseError(
            f"unexpected finish_reason: {choice.finish_reason}"
        )
    try:
        return cast(dict[str, Any], json.loads(raw))
    except json.JSONDecodeError as exc:
        log.warning("deepseek_json_parse_failed", error=str(exc), raw_preview=raw[:200])
        raise _RetryableResponseError("invalid JSON response") from exc


async def extract_json_with_retry(
    system: str,
    user: str,
    model: str | None = None,
    max_tokens: int = 400,
    temperature: float = 0.0,
    thinking: bool | None = None,
) -> dict[str, Any] | None:
    """Call DeepSeek with JSON mode. Returns parsed dict, or None on any failure.

    Failure modes that return None after three total attempts:
    - Transient API errors (5xx, network, etc.)
    - Empty, truncated, or otherwise non-JSON response content
    - A non-stop finish reason such as ``length`` or ``content_filter``
    """
    try:
        resolved_model = model or get_settings().deepseek_model
        return await _call(
            system, user, resolved_model, max_tokens, temperature, thinking
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("deepseek_call_failed", error=str(exc))
        return None
