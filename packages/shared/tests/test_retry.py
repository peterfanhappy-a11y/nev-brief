import pytest

from nev_shared.retry import retry_http, retry_llm, retry_resend


def test_retry_http_retries_on_exception():
    attempts = {"count": 0}

    @retry_http(max_attempts=3)
    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionError("fail")
        return "ok"

    assert flaky() == "ok"
    assert attempts["count"] == 3


def test_retry_http_gives_up_after_max():
    attempts = {"count": 0}

    @retry_http(max_attempts=2)
    def always_fail():
        attempts["count"] += 1
        raise ConnectionError("nope")

    with pytest.raises(ConnectionError):
        always_fail()
    assert attempts["count"] == 2


def test_retry_llm_decorator_exists():
    @retry_llm()
    def f():
        return "x"
    assert f() == "x"


def test_retry_resend_decorator_exists():
    @retry_resend()
    def f():
        return "x"
    assert f() == "x"
