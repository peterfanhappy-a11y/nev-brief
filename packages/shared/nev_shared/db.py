"""Supabase 客户端工厂 — 全局单例。所有服务通过 service_role key 访问，绕过 RLS。"""
from functools import lru_cache

from supabase import Client, create_client

from nev_shared.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)
