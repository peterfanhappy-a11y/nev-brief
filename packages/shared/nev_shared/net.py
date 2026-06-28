"""HTTP proxy env isolation helper.

Some third-party SDKs (Resend, etc.) hard-code requests.* calls with no
trust_env hook, so they pick up HTTP_PROXY/HTTPS_PROXY/ALL_PROXY from the
shell environment. When the cron host runs Clash / a SOCKS upstream that the
Python interpreter lacks support for (httpx requires the optional `socksio`
extra), the SDK call dies with "Using SOCKS proxy, but the 'socksio' package
is not installed".

Wrap such calls in `with no_proxy_env(): ...` to strip proxy env vars for the
duration of the block. The pop is process-local — it does not affect other
programs on the host, and the original values are restored on exit.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

_PROXY_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


@contextmanager
def no_proxy_env() -> Iterator[None]:
    saved = {k: os.environ.pop(k, None) for k in _PROXY_VARS}
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
