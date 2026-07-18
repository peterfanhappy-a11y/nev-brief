"""Gmail IMAP 客户端 —— Mac mini headless 读取 digest 邮件。

用应用专用密码（AI_GMAIL_IMAP_USER/PASSWORD）只读拉取。MIME 解析（parse_message）
是纯函数便于单测；fetch_latest 封装 imaplib 网络部分。

选「最新一封」：同一 subject 可能有重复/测试封，按邮件 Date 取最新。
"""
from __future__ import annotations

import email
import imaplib
import os
import socket
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime
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

    def __init__(self, host, port, proxy_host, proxy_port, *, timeout=None):  # noqa: ANN001
        self._proxy = (proxy_host, proxy_port)
        super().__init__(host, port, timeout=timeout)

    def _create_socket(self, timeout=None):  # noqa: ANN001
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
        return self.ssl_context.wrap_socket(sock, server_hostname=self.host)


def _connect(host: str, port: int, timeout: float) -> imaplib.IMAP4_SSL:
    proxy = _resolve_proxy()
    if proxy:
        pu = urlparse(proxy if "://" in proxy else f"http://{proxy}")
        log.info("ai_imap.via_proxy", proxy=f"{pu.hostname}:{pu.port}")
        return _ProxyIMAP4SSL(host, port, pu.hostname, pu.port or 8080, timeout=timeout)
    return imaplib.IMAP4_SSL(host, port, timeout=timeout)


@dataclass
class Attachment:
    filename: str
    content_type: str
    data: bytes


@dataclass
class DigestEmail:
    subject: str
    date: datetime
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


def parse_message(raw: bytes) -> DigestEmail:
    """把 RFC822 原始字节解析成 DigestEmail（纯函数）。"""
    msg: Message = email.message_from_bytes(raw)
    subject = _decode(msg.get("Subject"))
    try:
        dt = parsedate_to_datetime(msg.get("Date"))
    except (TypeError, ValueError):
        dt = datetime.now(timezone.utc)
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

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
            payload = part.get_payload(decode=True)
            if payload:
                attachments.append(
                    Attachment(
                        filename=filename or f"part-{len(attachments)+1}",
                        content_type=ctype or "application/octet-stream",
                        data=payload,
                    )
                )
            continue

        payload = part.get_payload(decode=True)
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

    return DigestEmail(subject=subject, date=dt, html=html, text=text, attachments=attachments)


def _date_key(text: str) -> tuple[int, int, int] | None:
    """从 subject 尾部抽 YYYY-M-D → (y,m,d)，容忍零填充漂移（2026-07-08 与 2026-7-8 等价）。"""
    import re

    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})\s*$", text.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def fetch_latest(
    sender: str,
    subject_prefix: str,
    date_str: str,
    *,
    host: str | None = None,
    user: str | None = None,
    password: str | None = None,
    mailbox: str = "INBOX",
    timeout: float = 30.0,
) -> DigestEmail | None:
    """取 from=sender、subject 以 subject_prefix 开头、且日期匹配 date_str 的最新一封。

    日期匹配容忍零填充漂移（上游 events 用 2026-07-08、builder 用 2026-7-8）。无匹配返回 None。
    """
    host = host or config.imap_host()
    user = user or config.imap_user()
    password = password or config.imap_password()
    if not user or not password:
        raise RuntimeError("Gmail IMAP 凭据缺失：设 AI_GMAIL_IMAP_USER / AI_GMAIL_IMAP_PASSWORD")

    target = _date_key(f"x-{date_str}")
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

        # 先只取 header（小），挑出日期匹配且最新的那封，再单独整封下载（省带宽/时延）
        best_uid: bytes | None = None
        best_dt: datetime | None = None
        for uid in uids:
            typ, hd = imap.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])")
            if typ != "OK" or not hd or not hd[0]:
                continue
            hdr = email.message_from_bytes(hd[0][1])
            subj = _decode(hdr.get("Subject")).strip()
            if not subj.startswith(subject_prefix):
                continue
            if target is not None and _date_key(subj) != target:
                continue
            try:
                dt = parsedate_to_datetime(hdr.get("Date"))
            except (TypeError, ValueError):
                dt = datetime.now(timezone.utc)
            if dt is not None and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if best_dt is None or dt > best_dt:
                best_dt, best_uid = dt, uid

        if best_uid is None:
            log.warning("ai_imap.no_date_match", prefix=subject_prefix, date=date_str)
            return None

        typ, msg_data = imap.fetch(best_uid, "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            log.warning("ai_imap.fetch_body_failed", prefix=subject_prefix, date=date_str)
            return None
        best = parse_message(msg_data[0][1])
        log.info(
            "ai_imap.fetched",
            subject=best.subject, date=str(best.date), attachments=len(best.attachments),
        )
        return best
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass
