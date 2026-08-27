import json

import pytest
from nev_shared.logger import configure_logging, get_logger


def test_get_logger_returns_bound_logger() -> None:
    log = get_logger("test-module")
    assert log is not None


def test_log_emits_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configure_logging(level="INFO", json_output=True)
    log = get_logger("test-module")
    log.info("hello", foo="bar")
    captured = capsys.readouterr()
    line = captured.out.strip().split("\n")[-1]
    parsed = json.loads(line)
    assert parsed["event"] == "hello"
    assert parsed["foo"] == "bar"
    assert parsed["logger"] == "test-module"
