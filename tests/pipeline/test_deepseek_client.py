"""Tests for nev_pipeline.deepseek_client (T7)."""
import pytest
import respx
from httpx import Response

from nev_pipeline.deepseek_client import extract_json_with_retry


@respx.mock(assert_all_called=False)
@pytest.mark.asyncio
async def test_extract_json_success(respx_mock):
    respx_mock.post("https://api.deepseek.com/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-chat",
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
    result = await extract_json_with_retry("sys prompt", "user prompt")
    assert result == {"brands": ["BYD"], "topics": ["new_car"]}


@respx.mock(assert_all_called=False)
@pytest.mark.asyncio
async def test_extract_json_invalid_returns_none(respx_mock):
    respx_mock.post("https://api.deepseek.com/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "not valid json {{"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    )
    result = await extract_json_with_retry("sys", "user")
    assert result is None


@respx.mock(assert_all_called=False)
@pytest.mark.asyncio
async def test_extract_json_api_error_returns_none(respx_mock):
    # 500 error after retries exhaust should return None, not raise
    respx_mock.post("https://api.deepseek.com/chat/completions").mock(
        return_value=Response(500, json={"error": "server error"})
    )
    result = await extract_json_with_retry("sys", "user")
    assert result is None
