import pytest

from nev_shared.config import Settings, get_settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    monkeypatch.setenv("RESEND_API_KEY", "re-key")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://feishu.x")
    monkeypatch.setenv("SENTRY_DSN", "https://x@sentry.io/1")
    get_settings.cache_clear()
    s = get_settings()
    assert s.supabase_url == "https://x.supabase.co"
    assert s.deepseek_api_key == "ds-key"


def test_settings_missing_required_raises(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(Exception):
        # _env_file=None bypasses real .env so the test isn't satisfied by
        # local secrets (config.py uses absolute-path .env by default).
        Settings(_env_file=None)
