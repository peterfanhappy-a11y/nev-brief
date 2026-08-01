from typing import Never

import pytest
from nev_shared.retry import retry_http, retry_llm, retry_resend


def test_retry_http_retries_on_exception() -> None:
    attempts = {"count": 0}

    @retry_http(max_attempts=3)
    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionError("fail")
        return "ok"

    assert flaky() == "ok"
    assert attempts["count"] == 3


def test_retry_http_gives_up_after_max() -> None:
    attempts = {"count": 0}

    @retry_http(max_attempts=2)
    def always_fail() -> Never:
        attempts["count"] += 1
        raise ConnectionError("nope")

    with pytest.raises(ConnectionError):
        always_fail()
    assert attempts["count"] == 2


def test_retry_llm_decorator_exists() -> None:
    @retry_llm()
    def f() -> str:
        return "x"
    assert f() == "x"


def test_retry_resend_decorator_exists() -> None:
    @retry_resend()
    def f() -> str:
        return "x"
    assert f() == "x"
