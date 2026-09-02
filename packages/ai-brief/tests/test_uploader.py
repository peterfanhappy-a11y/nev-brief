from __future__ import annotations

from types import SimpleNamespace

import httpx
from ai_brief.digest import uploader


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        supabase_url="https://storage.example",
        supabase_service_role_key="test-key",
    )


def _http_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://storage.example/upload")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("upload failed", request=request, response=response)


def test_upload_retries_server_error_then_returns_public_url(monkeypatch) -> None:
    calls = 0

    def post(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _http_error(520)
        return httpx.Response(200, request=httpx.Request("POST", "https://storage.example/upload"))

    monkeypatch.setattr(uploader, "get_settings", _settings)
    monkeypatch.setattr(uploader.httpx, "post", post)
    monkeypatch.setattr(
        uploader,
        "time",
        SimpleNamespace(sleep=lambda _seconds: None),
        raising=False,
    )

    url = uploader.upload_image(b"image", "image/png", path="ai/2026-09-02/today-ai.png")

    assert calls == 2
    assert url == "https://storage.example/storage/v1/object/public/ai-brief-images/ai/2026-09-02/today-ai.png"


def test_upload_retries_transport_error_then_returns_public_url(monkeypatch) -> None:
    calls = 0

    def post(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connection reset")
        return httpx.Response(200, request=httpx.Request("POST", "https://storage.example/upload"))

    monkeypatch.setattr(uploader, "get_settings", _settings)
    monkeypatch.setattr(uploader.httpx, "post", post)
    monkeypatch.setattr(
        uploader,
        "time",
        SimpleNamespace(sleep=lambda _seconds: None),
        raising=False,
    )

    assert uploader.upload_image(b"image", "image/png", path="ai/2026-09-02/today-ai.png")
    assert calls == 2


def test_upload_stops_after_three_transient_failures(monkeypatch) -> None:
    calls = 0

    def post(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise _http_error(520)

    monkeypatch.setattr(uploader, "get_settings", _settings)
    monkeypatch.setattr(uploader.httpx, "post", post)
    monkeypatch.setattr(
        uploader,
        "time",
        SimpleNamespace(sleep=lambda _seconds: None),
        raising=False,
    )

    assert uploader.upload_image(b"image", "image/png", path="ai/2026-09-02/today-ai.png") is None
    assert calls == 3


def test_upload_does_not_retry_client_error(monkeypatch) -> None:
    calls = 0

    def post(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise _http_error(401)

    monkeypatch.setattr(uploader, "get_settings", _settings)
    monkeypatch.setattr(uploader.httpx, "post", post)

    assert uploader.upload_image(b"image", "image/png", path="ai/2026-09-02/today-ai.png") is None
    assert calls == 1
