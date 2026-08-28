"""AI-brief 专属配置。

发件身份、品牌资产 URL、抓取行为参数。全部 env-overridable，Mac mini 与本地
保持一致无需改代码。共享的 Supabase / DeepSeek / Resend 凭据走 nev_shared.config。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 包根目录（config.py → ai_brief → ai-brief）
PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCES_YAML = PACKAGE_ROOT / "sources.yaml"
TEMPLATES_DIR = PACKAGE_ROOT / "templates"

# 工程根 .env（与 nev_shared.config 同一份）。pydantic-settings 只把 .env 灌进
# Settings 对象、不写 os.environ，故 digest/qwen 这些 .env-only 的密钥必须走这里读。
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class AiSettings(BaseSettings):
    """AI-brief 专属 .env 配置（IMAP / Qwen / digest 源）。字段名不区分大小写映射环境变量。"""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ai_digest_sender: str = "paul.fan.2200@gmail.com"
    ai_gmail_imap_host: str = "imap.gmail.com"
    ai_gmail_imap_user: str = ""
    ai_gmail_imap_password: str = ""
    ai_imap_proxy: str = ""   # Gmail 在 GFW 后需经 HTTP 代理隧道；空则回退 HTTPS_PROXY 环境变量
    ai_image_bucket: str = "ai-brief-images"

    # 发件身份（aivizens.com 需在 Resend 已验证）。可用 RESEND_FROM_EMAIL_AI 覆盖。
    resend_from_email_ai: str = "aivizens.daily@aivizens.com"
    resend_from_name_ai: str = "AIVIZENS 趋势"

    qwen_api_key: str = Field(
        default="", validation_alias=AliasChoices("qwen_api_key", "dashscope_api_key")
    )
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_vl_model: str = "qwen3.7-plus"


@lru_cache
def ai_settings() -> AiSettings:
    return AiSettings()

# ── 发件身份 ──────────────────────────────────────────────────────────
# 走 AiSettings 从 .env 读（os.environ 读不到 .env-only 值，之前误发成 onboarding@resend.dev）。
FROM_EMAIL = ai_settings().resend_from_email_ai
FROM_NAME = ai_settings().resend_from_name_ai

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

# ── 今日精选 四大模块（固定顺序 + 展示元数据）─────────────────────────
# key 对应 schema.Theme（内部键暂沿用旧名，内容生成重构时再改）；label 展示名；
# emoji 用于 intro bullets；color 用于分类标签文字色。
# 模块含义（内容生成方式下一轮定义）：
#   today_ai       今日AI     — 过去 24h 最重要 TOP3 新闻（结构待定，本轮先单条）
#   ai_masters     AI大神     — 24h 内最有观点/抓眼球的 AI 大神最新发表
#   llm_research    大模型研究 — 大模型相关研究
#   agent_research  智能体研究 — 智能体（agent）相关研究
THEMES: list[dict[str, str]] = [
    {"key": "model_research", "label": "今日AI", "emoji": "📰", "color": "#4F46E5"},
    {"key": "product_tools", "label": "AI大神", "emoji": "🎤", "color": "#DB2777"},
    {"key": "skills_efficiency", "label": "大模型研究", "emoji": "🧠", "color": "#0EA5E9"},
    {"key": "ethics_regulation", "label": "智能体研究", "emoji": "🤖", "color": "#10B981"},
    # 工具学习板块
    {"key": "ai_research", "label": "AI研究", "emoji": "🔬", "color": "#7C3AED"},
    {"key": "ai_engineering", "label": "AI工程", "emoji": "🛠️", "color": "#EA580C"},
    {"key": "agent_tools", "label": "Agent工具", "emoji": "🧰", "color": "#0891B2"},
]
THEME_ORDER = [t["key"] for t in THEMES]
THEME_META = {t["key"]: t for t in THEMES}

# ── Digest 摄取（今日AI / AI大神 从 Gmail digest 邮件取内容）───────────
# Mac mini headless 用 IMAP + 应用专用密码读 Gmail（MCP 只在 Claude 会话里可用）。
# 密钥走 AiSettings 从 .env 读（os.environ 里没有）。subject 前缀是常量。
DIGEST_EVENTS_SUBJECT_PREFIX = "ai-events-digest-"     # + YYYY-MM-DD(GMT+8)
DIGEST_BUILDER_SUBJECT_PREFIX = "follow-builder-digest-"
# 工具学习板块的 digest 源（同 sender，subject 前缀 + YYYY-MM-DD）
DIGEST_RESEARCH_SUBJECT_PREFIX = "ai-research-digest-"
DIGEST_ENGINEERING_SUBJECT_PREFIX = "ai-engineering-digest-"
DIGEST_AGENT_SUBJECT_PREFIX = "ai-agent-digest-"

# 压缩字数上限（软约束，DeepSeek prompt 里也会写）
TODAY_AI_TOP_N = 3                # 今日AI 取前几条（上游一次给 8 条，只用 TOP3）
TODAY_AI_SUMMARY_CHARS = 150      # 今日AI 每条正文
AI_MASTERS_SUMMARY_CHARS = 120    # AI大神 每条正文
AI_MASTERS_PICK_TOP5 = 2          # 前5条选几条
AI_MASTERS_PICK_FIRE5 = 3         # 后5条选几条
AI_RESEARCH_SUMMARY_CHARS = 200   # AI研究 单篇内容
AI_ENGINEERING_POINT_CHARS = 150  # AI工程 每条核心要点
AGENT_TOOL_SUMMARY_CHARS = 150    # Agent工具 每个工具介绍
AGENT_TOOLS_PICK = 3              # 过滤后展示 3 个工具
# 头图横幅裁剪（宽:高），源图多是长截图 → 裁成 banner；越大越矮
TODAY_AI_BANNER_ASPECT = 3.0
# 头图上传前缩到的最大宽度（研究图/工程图可能很大，缩小省邮件体积）
HEADER_IMAGE_MAX_WIDTH = 1000


# 下列从 .env 读的值用函数暴露（延迟到调用时读，便于测试注入 / 避免 import 期固化）
def digest_sender() -> str:
    return ai_settings().ai_digest_sender


def imap_host() -> str:
    return ai_settings().ai_gmail_imap_host


def imap_user() -> str:
    return ai_settings().ai_gmail_imap_user


def imap_password() -> str:
    return ai_settings().ai_gmail_imap_password


def imap_proxy() -> str:
    return ai_settings().ai_imap_proxy


def qwen_api_key() -> str:
    return ai_settings().qwen_api_key


def qwen_base_url() -> str:
    return ai_settings().qwen_base_url


def qwen_vl_model() -> str:
    return ai_settings().qwen_vl_model


def image_bucket() -> str:
    return ai_settings().ai_image_bucket


def email_send_enabled() -> bool:
    """Global kill switch; sending stays disabled unless explicitly enabled."""
    return os.environ.get("AI_EMAIL_SEND_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


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


# DeepSeek 模型：deepseek-chat 是当前有效的通用模型。不用 settings.deepseek_model
# （共享 .env 里可能是 NEV 用的别名 deepseek-v4-pro，AI 管线的 API 会拒绝）。
# 需要覆盖时设 DEEPSEEK_MODEL_AI 环境变量。
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL_AI", "deepseek-chat")


def get_model() -> str:
    return DEEPSEEK_MODEL
