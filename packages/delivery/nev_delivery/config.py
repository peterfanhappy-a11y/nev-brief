"""Delivery-specific config: from address, from name, unsubscribe header.

All three are env-overridable so Mac mini and Vercel can stay in lockstep
without code changes when the verified domain or web URL flips.
"""
from __future__ import annotations

import os

# Use Resend's own domain until aivizens.com is verified in Resend Dashboard.
# Then set RESEND_FROM_EMAIL=morning-brief@aivizens.com in Mac mini's .env.
FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
FROM_NAME = os.environ.get("RESEND_FROM_NAME", "NEV 早报")

# RFC 8058 List-Unsubscribe header — Gmail renders the top-bar unsubscribe.
# Must match a live route on whichever domain WEB_BASE_URL points to.
_web_base = os.environ.get("WEB_BASE_URL", "https://aivizens.com").rstrip("/")
LIST_UNSUBSCRIBE_PREFIX = f"{_web_base}/unsubscribe?token="
