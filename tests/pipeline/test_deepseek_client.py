"""Tests for nev_pipeline.deepseek_client (T7)."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import respx
from httpx import Response
from nev_pipeline.deepseek_client import extract_json_with_retry


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        deepseek_api_key="test-key",
        deepseek_base_url="https://api.deepseek.com",
        deepseek_model="deepseek-flash",
    )


def _completion(content: str, *, finish_reason: str = "stop") -> Response:
    return Response(
        200,
        json={
            "id": "x",
            "object": "chat.completion",
            "created": 0,
            "model": "deepseek-flash",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": finish_reason,
                }
            ],
        },
    )


@respx.mock(assert_all_called=False)
@pytest.mark.asyncio
async def test_extract_json_success(respx_mock):
    route = respx_mock.post("https://api.deepseek.com/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '{"brands": ["BYD"], "topics": ["new_car"]}',
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    )
    with patch("nev_pipeline.deepseek_client.get_settings", return_value=_settings()):
        result = await extract_json_with_retry("sys prompt", "user prompt")
    assert result == {"brands": ["BYD"], "topics": ["new_car"]}
    assert len(route.calls) == 1
    request_body = json.loads(route.calls.last.request.content)
    assert request_body["model"] == "deepseek-flash"


@respx.mock(assert_all_called=False)
@pytest.mark.asyncio
async def test_extract_json_invalid_returns_none(respx_mock):
    route = respx_mock.post("https://api.deepseek.com/chat/completions").mock(
        return_value=_completion("not valid json {{")
    )
    with patch("nev_pipeline.deepseek_client.get_settings", return_value=_settings()):
        result = await extract_json_with_retry("sys", "user")
    assert result is None
    assert len(route.calls) == 3


@pytest.mark.parametrize("invalid_content", ['{"subject":"truncated', ""])
@respx.mock(assert_all_called=False)
@pytest.mark.asyncio
async def test_extract_json_retries_invalid_content_then_recovers(
    respx_mock, invalid_content: str
):
    route = respx_mock.post("https://api.deepseek.com/chat/completions").mock(
        side_effect=[
            _completion(invalid_content),
            _completion('{"subject":"complete"}'),
        ]
    )

    with patch("nev_pipeline.deepseek_client.get_settings", return_value=_settings()):
        result = await extract_json_with_retry("sys", "user")

    assert result == {"subject": "complete"}
    assert len(route.calls) == 2


@respx.mock(assert_all_called=False)
@pytest.mark.asyncio
async def test_extract_json_retries_non_stop_finish_reason(respx_mock):
    route = respx_mock.post("https://api.deepseek.com/chat/completions").mock(
        side_effect=[
            _completion('{"subject":"partial"}', finish_reason="length"),
            _completion('{"subject":"complete"}'),
        ]
    )

    with patch("nev_pipeline.deepseek_client.get_settings", return_value=_settings()):
        result = await extract_json_with_retry("sys", "user")

    assert result == {"subject": "complete"}
    assert len(route.calls) == 2


@respx.mock(assert_all_called=False)
@pytest.mark.asyncio
async def test_extract_json_api_error_returns_none(respx_mock):
    # 500 error after retries exhaust should return None, not raise
    route = respx_mock.post("https://api.deepseek.com/chat/completions").mock(
        return_value=Response(500, json={"error": "server error"})
    )
    with patch("nev_pipeline.deepseek_client.get_settings", return_value=_settings()):
        result = await extract_json_with_retry("sys", "user")
    assert result is None
    assert len(route.calls) == 3


@pytest.mark.asyncio
async def test_extract_json_missing_settings_returns_none():
    with patch(
        "nev_pipeline.deepseek_client.get_settings",
        side_effect=RuntimeError("missing configuration"),
    ):
        result = await extract_json_with_retry("sys", "user")

    assert result is None
