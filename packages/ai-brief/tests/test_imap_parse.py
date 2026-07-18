"""imap_client.parse_message —— MIME 解析纯函数测试（不触网）。"""
from __future__ import annotations

from email.message import EmailMessage

from ai_brief.digest.imap_client import parse_message


def _build_raw() -> bytes:
    msg = EmailMessage()
    msg["Subject"] = "ai-events-digest-2026-07-06"
    msg["From"] = "paul.fan.2200@gmail.com"
    msg["To"] = "peter.fan.happy@gmail.com"
    msg["Date"] = "Sun, 06 Jul 2026 06:11:21 +0800"
    msg.set_content("纯文本兜底")
    msg.add_alternative("<h2>今日AI</h2><p>正文</p>", subtype="html")
    msg.add_attachment(
        b"\x89PNG\r\n\x1a\n-fake-01", maintype="image", subtype="png",
        filename="01-anthropic-sonnet5.png",
    )
    msg.add_attachment(
        b"\x89PNG\r\n\x1a\n-fake-02", maintype="image", subtype="png",
        filename="02-baidu-wenxin5.png",
    )
    return msg.as_bytes()


def test_parse_extracts_html_text_and_images() -> None:
    d = parse_message(_build_raw())
    assert d.subject == "ai-events-digest-2026-07-06"
    assert d.html and "今日AI" in d.html
    assert d.text and "纯文本兜底" in d.text
    imgs = d.image_attachments()
    assert [a.filename for a in imgs] == ["01-anthropic-sonnet5.png", "02-baidu-wenxin5.png"]
    assert imgs[0].content_type == "image/png"
    assert imgs[0].data.endswith(b"-fake-01")


def test_parse_date_parsed_with_tz() -> None:
    d = parse_message(_build_raw())
    assert d.date.year == 2026 and d.date.month == 7 and d.date.day == 6
    assert d.date.tzinfo is not None
