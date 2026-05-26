import json
import logging

from nev_shared.logger import get_logger, configure_logging


def test_get_logger_returns_bound_logger():
    log = get_logger("test-module")
    assert log is not None


def test_log_emits_json(capsys, monkeypatch):
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
