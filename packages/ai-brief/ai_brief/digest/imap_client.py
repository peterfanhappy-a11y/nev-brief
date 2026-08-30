"""Gmail IMAP 客户端 —— Mac mini headless 读取 digest 邮件。

用应用专用密码（AI_GMAIL_IMAP_USER/PASSWORD）只读拉取。MIME 解析（parse_message）
是纯函数便于单测；fetch_latest 封装 imaplib 网络部分。

选「最新一封」：同一 subject 可能有重复/测试封，按 Gmail INTERNALDATE 取最新。
"""
from __future__ import annotations

import email
import imaplib
import os
import re
import socket
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import cast
from urllib.parse import urlparse

from nev_shared.logger import get_logger

from ai_brief import config

log = get_logger("ai_brief.imap")


def _resolve_proxy() -> str:
    """Gmail 在 GFW 后需经代理。优先 AI_IMAP_PROXY，回退 HTTPS_PROXY/HTTP_PROXY。"""
    return (
        config.imap_proxy()
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
        or ""
    ).strip()


class _ProxyIMAP4SSL(imaplib.IMAP4_SSL):
    """经 HTTP CONNECT 代理隧道连 IMAPS —— 供 GFW 后的机器读 Gmail。"""

    def __init__(
        self,
        host: str,
        port: int,
        proxy_host: str,
        proxy_port: int,
        *,
        timeout: float | None = None,
    ) -> None:
        self._proxy = (proxy_host, proxy_port)
        super().__init__(host, port, timeout=timeout)

    def _create_socket(self, timeout: float | None = None) -> socket.socket:
        sock = socket.create_connection(self._proxy, timeout=timeout)
        target = f"{self.host}:{self.port}"
        req = f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\nProxy-Connection: keep-alive\r\n\r\n"
        sock.sendall(req.encode("ascii"))
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = sock.recv(4096)
            if not chunk:
                break
            resp += chunk
        status = resp.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        if " 200 " not in status:
            sock.close()
            raise OSError(f"IMAP 代理 CONNECT 失败：{status or '空响应'}")
        return cast(
            socket.socket,
            self.ssl_context.wrap_socket(sock, server_hostname=self.host),
        )


def _connect(host: str, port: int, timeout: float) -> imaplib.IMAP4_SSL:
    proxy = _resolve_proxy()
    if proxy:
        pu = urlparse(proxy if "://" in proxy else f"http://{proxy}")
        log.info("ai_imap.via_proxy", proxy=f"{pu.hostname}:{pu.port}")
        return _ProxyIMAP4SSL(
            host,
            port,
            cast(str, pu.hostname),
            pu.port or 8080,
            timeout=timeout,
        )
    return imaplib.IMAP4_SSL(host, port, timeout=timeout)


@dataclass
class Attachment:
    filename: str
    content_type: str
    data: bytes


@dataclass
class DigestEmail:
    subject: str
    received_at: datetime
    sent_at: datetime | None = None
    message_id: str = ""
    html: str | None = None
    text: str | None = None
    attachments: list[Attachment] = field(default_factory=list)

    def image_attachments(self) -> list[Attachment]:
        return [a for a in self.attachments if a.content_type.startswith("image/")]


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return value


def parse_message(raw: bytes, *, received_at: datetime) -> DigestEmail:
    """把 RFC822 原始字节解析成 DigestEmail（纯函数）。"""
    msg: Message = email.message_from_bytes(raw)
    message_id = _decode(msg.get("Message-ID")).strip()
    subject = _decode(msg.get("Subject"))
    sent_at: datetime | None = None
    sent_header = msg.get("Date")
    if sent_header:
        with suppress(TypeError, ValueError):
            sent_at = parsedate_to_datetime(sent_header)
    if sent_at is not None and sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=UTC)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    else:
        received_at = received_at.astimezone(UTC)

    html: str | None = None
    text: str | None = None
    attachments: list[Attachment] = []

    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = (part.get_content_type() or "").lower()
        disp = (part.get("Content-Disposition") or "").lower()
        filename = _decode(part.get_filename())

        if filename or "attachment" in disp or ctype.startswith("image/"):
            payload = cast(bytes | None, part.get_payload(decode=True))
            if payload:
                attachments.append(
                    Attachment(
                        filename=filename or f"part-{len(attachments)+1}",
                        content_type=ctype or "application/octet-stream",
                        data=payload,
                    )
                )
            continue

        payload = cast(bytes | None, part.get_payload(decode=True))
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            body = payload.decode(charset, errors="replace")
        except LookupError:
            body = payload.decode("utf-8", errors="replace")
        if ctype == "text/html" and html is None:
            html = body
        elif ctype == "text/plain" and text is None:
            text = body

    return DigestEmail(
        subject=subject,
        received_at=received_at,
        sent_at=sent_at,
        message_id=message_id,
        html=html,
        text=text,
        attachments=attachments,
    )


def _date_key(text: str) -> tuple[int, int, int] | None:
    """从 subject 尾部抽 YYYY-M-D → (y,m,d)，容忍零填充漂移（2026-07-08 与 2026-7-8 等价）。"""
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})\s*$", text.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


_INTERNALDATE_RE = re.compile(br'INTERNALDATE "(?P<value>[^"]+)"')


def _internaldate(response: bytes) -> datetime | None:
    """Parse the trusted IMAP receipt timestamp from a FETCH response."""
    match = _INTERNALDATE_RE.search(response)
    if match is None:
        return None
    try:
        value = match.group("value").decode("ascii")
        parsed = parsedate_to_datetime(value)
    except (UnicodeDecodeError, TypeError, ValueError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _fetch_latest_once(
    sender: str,
    subject_prefix: str,
    date_str: str | None,
    *,
    host: str | None = None,
    user: str | None = None,
    password: str | None = None,
    mailbox: str = "INBOX",
    timeout: float = 30.0,
    within_hours: float | None = None,
) -> DigestEmail | None:
    """取 from=sender、subject 以 subject_prefix 开头、且日期匹配 date_str 的最新一封。

    date_str=None → 不按日期过滤，取该前缀最新一封（用于日期标签漂移的源做回退）。
    within_hours 设置时，忽略 Gmail INTERNALDATE 早于该窗口的邮件。
    日期匹配容忍零填充漂移（上游 events 用 2026-07-08、builder 用 2026-7-8）。无匹配返回 None。
    """
    host = host or config.imap_host()
    user = user or config.imap_user()
    password = password or config.imap_password()
    if not user or not password:
        raise RuntimeError("Gmail IMAP 凭据缺失：设 AI_GMAIL_IMAP_USER / AI_GMAIL_IMAP_PASSWORD")

    target = _date_key(f"x-{date_str}") if date_str else None
    oldest_ok = (
        datetime.now(UTC) - timedelta(hours=within_hours)
        if within_hours else None
    )
    imap = _connect(host, 993, timeout)
    try:
        imap.login(user, password)
        imap.select(mailbox, readonly=True)
        # IMAP SUBJECT 是子串匹配；用前缀粗筛，日期在客户端精确比对
        typ, data = imap.search(None, "FROM", f'"{sender}"', "SUBJECT", f'"{subject_prefix}"')
        if typ != "OK" or not data or not data[0]:
            log.warning("ai_imap.no_match", sender=sender, prefix=subject_prefix)
            return None
        uids = data[0].split()

        # 先只取 header + INTERNALDATE（小），按服务器收件时间挑最新，再下载整封。
        best_uid: bytes | None = None
        best_received_at: datetime | None = None
        for uid in uids:
            typ, hd = imap.fetch(
                cast(str, uid),
                "(INTERNALDATE BODY.PEEK[HEADER.FIELDS (SUBJECT DATE MESSAGE-ID)])",
            )
            if typ != "OK" or not hd or not hd[0]:
                continue
            header_data = cast(tuple[bytes, bytes], hd[0])[1]
            hdr = email.message_from_bytes(header_data)
            subj = _decode(hdr.get("Subject")).strip()
            if not subj.startswith(subject_prefix):
                continue
            if target is not None and _date_key(subj) != target:
                continue
            received_at = _internaldate(cast(tuple[bytes, bytes], hd[0])[0])
            if received_at is None:
                log.warning("ai_imap.internaldate_missing", uid=uid)
                continue
            if oldest_ok is not None and received_at < oldest_ok:
                continue
            if best_received_at is None or received_at > best_received_at:
                best_received_at, best_uid = received_at, uid

        if best_uid is None:
            log.warning("ai_imap.no_date_match", prefix=subject_prefix, date=date_str)
            return None

        typ, msg_data = imap.fetch(cast(str, best_uid), "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            log.warning("ai_imap.fetch_body_failed", prefix=subject_prefix, date=date_str)
            return None
        message_data = cast(tuple[bytes, bytes], msg_data[0])[1]
        if best_received_at is None:
            log.warning("ai_imap.internaldate_missing", uid=best_uid)
            return None
        best = parse_message(message_data, received_at=best_received_at)
        log.info(
            "ai_imap.fetched",
            subject=best.subject,
            received_at=str(best.received_at),
            sent_at=str(best.sent_at),
            attachments=len(best.attachments),
        )
        return best
    finally:
        # Logout is best-effort during cleanup; the fetch result/error must win.
        with suppress(Exception):  # noqa: S110
            imap.logout()


def fetch_latest(
    sender: str,
    subject_prefix: str,
    date_str: str | None,
    *,
    host: str | None = None,
    user: str | None = None,
    password: str | None = None,
    mailbox: str = "INBOX",
    timeout: float = 30.0,
    within_hours: float | None = None,
) -> DigestEmail | None:
    """Fetch one digest, retrying one transient IMAP connection loss."""
    host = host or config.imap_host()
    user = user or config.imap_user()
    password = password or config.imap_password()
    if not user or not password:
        raise RuntimeError("Gmail IMAP 凭据缺失：设 AI_GMAIL_IMAP_USER / AI_GMAIL_IMAP_PASSWORD")

    for attempt in range(2):
        try:
            return _fetch_latest_once(
                sender,
                subject_prefix,
                date_str,
                host=host,
                user=user,
                password=password,
                mailbox=mailbox,
                timeout=timeout,
                within_hours=within_hours,
            )
        except (imaplib.IMAP4.abort, OSError):
            if attempt == 1:
                raise
            log.warning("ai_imap.retrying_connection", attempt=attempt + 1)

    raise AssertionError("unreachable")
