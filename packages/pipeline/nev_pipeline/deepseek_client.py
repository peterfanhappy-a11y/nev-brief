"""DeepSeek client (T7) — OpenAI-compatible SDK wrapper with retry + JSON parse fallback.

DeepSeek exposes an OpenAI-compatible /chat/completions endpoint, so we reuse the
official openai Python SDK (which uses httpx under the hood — hence respx for tests).

Failure path returns None so callers (e.g. entity_extractor) can fall back to dict-based
extraction. Acceptance gate 4: "DeepSeek JSON 解析失败时 fallback 到 entity_dict.yaml 命中".
"""
from __future__ import annotations

import json
import logging

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

# Retry only transient errors. Auth / bad-request / quota errors fail fast
# (no point waiting through exponential backoff when the key is wrong).
_RETRYABLE = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
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
) -> str:
    resp = await _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


async def extract_json_with_retry(
    system: str,
    user: str,
    model: str = "deepseek-chat",
    max_tokens: int = 400,
    temperature: float = 0.0,
) -> dict | None:
    """Call DeepSeek with JSON mode. Returns parsed dict, or None on any failure.

    Failure modes that return None:
    - API errors after retries (5xx, network, etc.)
    - Non-JSON response body (model ignored json_object mode)
    """
    try:
        raw = await _call(system, user, model, max_tokens, temperature)
    except Exception as exc:  # noqa: BLE001
        log.warning("deepseek_call_failed", error=str(exc))
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("deepseek_json_parse_failed", error=str(exc), raw_preview=raw[:200])
        return None
