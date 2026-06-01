"""Delivery-specific config: from address, from name, unsubscribe header.

These are constants for MVP; once a custom domain is set up they should move
to env vars (FROM_EMAIL / FROM_NAME).
"""
from __future__ import annotations

# MVP: 使用 Resend 自有域名（不需要验证 DNS）。Gmail 不挑剔 from。
# 后续：买域名后改 morning-brief@<your-domain>，并在 Resend Dashboard 验证 DNS。
FROM_EMAIL = "onboarding@resend.dev"
FROM_NAME = "NEV 早报"

# RFC 8058 List-Unsubscribe header — Gmail 会自动渲染顶部退订按钮
LIST_UNSUBSCRIBE_PREFIX = "https://nev-brief.vercel.app/unsubscribe?token="
