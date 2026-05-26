"""统一的 tenacity 重试装饰器 — 各模块不要自己实现 try/except 循环。"""
from typing import Any, Callable, TypeVar

from tenacity import (
    retry, stop_after_attempt, wait_exponential, wait_fixed, wait_random,
    retry_if_exception_type,
)

F = TypeVar("F", bound=Callable[..., Any])


def retry_http(max_attempts: int = 3) -> Callable[[F], F]:
    """爬虫 HTTP / Supabase 调用 — 1s/4s/16s 指数退避 + 抖动。

    Spec §7.2
    """
    return retry(  # type: ignore[return-value]
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=16) + wait_random(0, 0.5),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )


def retry_llm(max_attempts: int = 3) -> Callable[[F], F]:
    """DeepSeek API — 2s/8s/30s。"""
    return retry(  # type: ignore[return-value]
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )


def retry_resend(max_attempts: int = 3) -> Callable[[F], F]:
    """Resend 邮件发送 — 5s/30s/5min（避免触发反垃圾）。"""
    return retry(  # type: ignore[return-value]
        stop=stop_after_attempt(max_attempts),
        wait=wait_fixed(5) + wait_random(0, 5),  # 简化：5-10s 固定退避
        reraise=True,
    )


def retry_db(max_attempts: int = 3) -> Callable[[F], F]:
    """Supabase 写入 — 0.5s/2s/8s。"""
    return retry(  # type: ignore[return-value]
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        reraise=True,
    )
