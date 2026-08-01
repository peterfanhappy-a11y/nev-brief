import importlib
import sys
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
    tmp_path: Path,
) -> None:
    """Copying the root example preserves defaults without importing local credentials."""
    environment_keys = (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "DATABASE_URL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_MODEL_AI",
        "RESEND_API_KEY",
        "FEISHU_WEBHOOK_URL",
        "SENTRY_DSN",
        "HEALTHCHECKS_PING_URL",
        "ADMIN_TOKEN",
        "CRAWL_MAX_QPS_PER_DOMAIN",
        "LOG_LEVEL",
        "AI_DIGEST_SENDER",
        "AI_GMAIL_IMAP_HOST",
        "AI_GMAIL_IMAP_USER",
        "AI_GMAIL_IMAP_PASSWORD",
        "AI_IMAP_PROXY",
        "AI_IMAGE_BUCKET",
        "RESEND_FROM_EMAIL_AI",
        "RESEND_FROM_NAME_AI",
        "QWEN_API_KEY",
        "DASHSCOPE_API_KEY",
        "QWEN_BASE_URL",
        "QWEN_VL_MODEL",
        "WEB_BASE_URL",
    )
    for key in environment_keys:
        monkeypatch.delenv(key, raising=False)

    env_example = Path(__file__).resolve().parents[3] / ".env.example"
    monkeypatch.chdir(tmp_path)
    inert_import_environment = {
        "SUPABASE_URL": "https://example.invalid",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role",
        "DEEPSEEK_API_KEY": "test-deepseek",
        "DEEPSEEK_MODEL_AI": "test-deepseek-model",
        "RESEND_API_KEY": "test-resend",
        "WEB_BASE_URL": "https://example.invalid",
        "AI_DIGEST_SENDER": "digest@example.invalid",
        "AI_GMAIL_IMAP_HOST": "imap.example.invalid",
        "AI_GMAIL_IMAP_USER": "reader@example.invalid",
        "AI_GMAIL_IMAP_PASSWORD": "test-password",
        "AI_IMAP_PROXY": "http://127.0.0.1:9",
        "AI_IMAGE_BUCKET": "test-image-bucket",
        "RESEND_FROM_EMAIL_AI": "isolated-sender@example.invalid",
        "RESEND_FROM_NAME_AI": "Isolated Sender",
        "QWEN_API_KEY": "test-qwen",
        "QWEN_BASE_URL": "https://example.invalid",
        "QWEN_VL_MODEL": "test-qwen-model",
    }
    for key, value in inert_import_environment.items():
        monkeypatch.setenv(key, value)

    ai_brief_package = importlib.import_module("ai_brief")
    previous_config_module = sys.modules.pop("ai_brief.config", None)
    missing_attribute = object()
    previous_config_attribute = getattr(ai_brief_package, "config", missing_attribute)
    if previous_config_attribute is not missing_attribute:
        delattr(ai_brief_package, "config")

    try:
        ai_config = importlib.import_module("ai_brief.config")
        assert ai_config.FROM_EMAIL == "isolated-sender@example.invalid"
        assert ai_config.FROM_NAME == "Isolated Sender"
        assert ai_config.qwen_vl_model() == "test-qwen-model"

        for key in inert_import_environment:
            monkeypatch.delenv(key, raising=False)

        settings = Settings(_env_file=env_example)  # type: ignore[call-arg]
        ai_settings = ai_config.AiSettings(_env_file=env_example)

        assert settings.deepseek_base_url == "https://api.deepseek.com"
        assert settings.deepseek_model == "deepseek-chat"
        assert settings.crawl_max_qps_per_domain == 1.0
        assert settings.log_level == "INFO"
        assert ai_settings.qwen_vl_model == "qwen3.7-plus"
    finally:
        sys.modules.pop("ai_brief.config", None)
        if previous_config_module is not None:
            sys.modules["ai_brief.config"] = previous_config_module
        if previous_config_attribute is missing_attribute:
            if hasattr(ai_brief_package, "config"):
                delattr(ai_brief_package, "config")
        else:
            ai_brief_package.__dict__["config"] = previous_config_attribute
