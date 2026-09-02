"""把 digest 头图转存到 Supabase Storage 公开桶，返回可热链的公开 URL。

邮件不能热链 Gmail 附件（需鉴权），所以每天把选中的头图上传一次到公开桶，
所有订阅者共用同一 URL（同 og_image 模式）。用 service-role key 走 Storage REST。
"""
from __future__ import annotations

import hashlib
import time

import httpx
from nev_shared.config import get_settings
from nev_shared.logger import get_logger

from ai_brief import config

log = get_logger("ai_brief.uploader")

_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _is_transient_upload_error(error: Exception) -> bool:
    if isinstance(error, httpx.TransportError):
        return True
    return isinstance(error, httpx.HTTPStatusError) and error.response.status_code >= 500


def upload_image(
    data: bytes,
    content_type: str,
    *,
    path: str,
    bucket: str | None = None,
    timeout: float = 30.0,
) -> str | None:
    """上传到 {bucket}/{path}，覆盖式（x-upsert）。返回公开 URL，失败返回 None。"""
    settings = get_settings()
    bucket = bucket or config.image_bucket()
    base = settings.supabase_url.rstrip("/")
    key = settings.supabase_service_role_key
    for attempt in range(3):
        try:
            resp = httpx.post(
                f"{base}/storage/v1/object/{bucket}/{path}",
                headers={
                    "Authorization": f"Bearer {key}",
                    "apikey": key,
                    "Content-Type": content_type or "image/png",
                    "x-upsert": "true",
                    "cache-control": "3600",
                },
                content=data,
                timeout=timeout,
                trust_env=False,
            )
            resp.raise_for_status()
            break
        except Exception as e:  # noqa: BLE001
            if _is_transient_upload_error(e) and attempt < 2:
                log.warning("ai_uploader.retrying", path=path, attempt=attempt + 1)
                time.sleep(attempt + 1)
                continue
            log.warning("ai_uploader.failed", path=path, err=str(e)[:200])
            return None

    public_url = f"{base}/storage/v1/object/public/{bucket}/{path}"
    log.info("ai_uploader.uploaded", path=path)
    return public_url


def image_path(brief_date: str, module: str, data: bytes, content_type: str) -> str:
    """稳定路径：ai/<date>/<module>-<hash8>.<ext>，同日重跑幂等覆盖。"""
    ext = _EXT.get((content_type or "").lower(), "png")
    h = hashlib.sha256(data).hexdigest()[:8]
    return f"ai/{brief_date}/{module}-{h}.{ext}"
