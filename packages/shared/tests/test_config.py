from pathlib import Path

import pytest
from nev_shared.config import Settings, get_settings
from pydantic import ValidationError


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_settings_missing_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        # _env_file=None bypasses real .env so the test isn't satisfied by
        # local secrets (config.py uses absolute-path .env by default).
        # pydantic-settings accepts this runtime keyword through its generated init.
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_root_env_example_constructs_settings_with_code_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Copying the root example must preserve typed defaults instead of parsing blanks."""
    for key in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "DATABASE_URL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "RESEND_API_KEY",
        "FEISHU_WEBHOOK_URL",
        "SENTRY_DSN",
        "HEALTHCHECKS_PING_URL",
        "ADMIN_TOKEN",
        "CRAWL_MAX_QPS_PER_DOMAIN",
        "LOG_LEVEL",
    ):
        monkeypatch.delenv(key, raising=False)

    env_example = Path(__file__).resolve().parents[3] / ".env.example"
    settings = Settings(_env_file=env_example)  # type: ignore[call-arg]

    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_model == "deepseek-chat"
    assert settings.crawl_max_qps_per_domain == 1.0
    assert settings.log_level == "INFO"
