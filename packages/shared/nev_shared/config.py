from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """所有服务共享的环境配置。

    Secrets 必须通过 .env 或环境变量提供。本地：.env 文件；CI：GitHub Secrets；
    生产：Mac mini ~/nev-brief/.env (chmod 600)。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase
    supabase_url: str
    supabase_service_role_key: str

    # External APIs
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    resend_api_key: str

    # Monitoring
    feishu_webhook_url: str
    sentry_dsn: str | None = None
    healthchecks_ping_url: str | None = None

    # Admin
    admin_token: str = Field(default="change-me-please")

    # Behavior
    crawl_max_qps_per_domain: float = 1.0
    deepseek_model: str = "deepseek-chat"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
