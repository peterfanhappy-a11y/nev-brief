from unittest.mock import patch

from nev_shared.db import get_supabase_client


def test_get_supabase_client_returns_singleton(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setenv("RESEND_API_KEY", "x")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "x")

    from nev_shared.config import get_settings
    get_settings.cache_clear()
    get_supabase_client.cache_clear()

    with patch("nev_shared.db.create_client") as mock_create:
        mock_create.return_value = "supabase_client"
        c1 = get_supabase_client()
        c2 = get_supabase_client()
        assert c1 is c2
        mock_create.assert_called_once()
