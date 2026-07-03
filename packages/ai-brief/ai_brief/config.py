"""AI-brief 专属配置。

发件身份、品牌资产 URL、抓取行为参数。全部 env-overridable，Mac mini 与本地
保持一致无需改代码。共享的 Supabase / DeepSeek / Resend 凭据走 nev_shared.config。
"""
from __future__ import annotations

import os
from pathlib import Path

# 包根目录（config.py → ai_brief → ai-brief）
PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCES_YAML = PACKAGE_ROOT / "sources.yaml"
TEMPLATES_DIR = PACKAGE_ROOT / "templates"

# ── 发件身份 ──────────────────────────────────────────────────────────
# aivizens.com 在 Resend 已验证；未配置时回落到 NEV 的验证发件地址。
FROM_EMAIL = os.environ.get(
    "RESEND_FROM_EMAIL_AI",
    os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev"),
)
FROM_NAME = os.environ.get("RESEND_FROM_NAME_AI", "AIVIZENS 趋势")

# ── Web 基址 ──────────────────────────────────────────────────────────
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "https://aivizens.com").rstrip("/")
UNSUBSCRIBE_PREFIX = f"{WEB_BASE_URL}/unsubscribe?token="
RATE_BASE_URL = f"{WEB_BASE_URL}/api/ai/rate"

# ── 品牌资产（邮件热链，必须公开可访问）────────────────────────────────
AUTHOR_NAME = "Fan's Fans"
AUTHOR_PHOTO_URL = f"{WEB_BASE_URL}/brand/author.png"
LOGO_EMAIL_URL = f"{WEB_BASE_URL}/brand/logo-email.png"
BANNER_TAGLINE = "Together with 不凡的数智生活"
SOCIAL_ICONS = [
    ("微博", f"{WEB_BASE_URL}/brand/companies/weibo.png", "#"),
    ("微信", f"{WEB_BASE_URL}/brand/companies/wechat.png", "#"),
    ("抖音", f"{WEB_BASE_URL}/brand/companies/douyin.png", "#"),
    ("小红书", f"{WEB_BASE_URL}/brand/companies/xiaohongshu.png", "#"),
]

# ── 四大主题（固定顺序 + 展示元数据）──────────────────────────────────
# key 对应 schema.Theme；label 展示名；emoji 用于 intro bullets；color 用于无图色块兜底。
THEMES: list[dict[str, str]] = [
    {"key": "model_research", "label": "模型研究", "emoji": "🧠", "color": "#4F46E5"},
    {"key": "product_tools", "label": "产品工具", "emoji": "🛠", "color": "#0EA5E9"},
    {"key": "skills_efficiency", "label": "Skills 效率", "emoji": "⚡", "color": "#F59E0B"},
    {"key": "ethics_regulation", "label": "伦理监管", "emoji": "⚖️", "color": "#10B981"},
]
THEME_ORDER = [t["key"] for t in THEMES]
THEME_META = {t["key"]: t for t in THEMES}

# ── 抓取行为 ──────────────────────────────────────────────────────────
CRAWL_USER_AGENT = "AIVIZENS-Bot/1.0 (+https://aivizens.com/about)"
CRAWL_MIN_INTERVAL_S = 2.0        # 每源逐篇抓取的最小间隔
CRAWL_TIMEOUT_S = 20.0
CRAWL_MAX_ARTICLES_PER_SOURCE = 20  # 每源每次最多抓多少篇文章页
ARTICLE_CONTENT_MAX_CHARS = 8000    # 正文存储上限

# ── DeepSeek 生成参数 ─────────────────────────────────────────────────
STAGE1_MAX_CANDIDATES = 150       # Stage-1 送入的候选文章数上限
STAGE1_SNIPPET_CHARS = 200        # Stage-1 每篇附带的正文首段长度
STAGE2_ARTICLE_CHARS = 3000       # Stage-2 每篇选中文章正文截断长度
STAGE2_MAX_TOKENS = 4000
STAGE2_TEMPERATURE = 0.4

# 24h 抓取窗口（select 拉取候选时用）
CANDIDATE_WINDOW_HOURS = 24


def get_model() -> str:
    """DeepSeek 模型名。走 nev_shared 共享配置（默认 deepseek-chat）。"""
    from nev_shared.config import get_settings

    return get_settings().deepseek_model
