"""AIVIZENS AI 趋势 — 每日 AI 简报独立管线。

与 NEV 产线完全隔离：独立 crawler（抓正文）、独立 Supabase 表（ai_*）、
独立 daily run（独立 launchd plist）。仅 import 共享纯库函数（feishu、net），
不修改任何 NEV 代码。
"""
