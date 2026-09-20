import importlib
import os

import pytest
from ai_brief import config


def test_default_deepseek_model_is_flash(monkeypatch: pytest.MonkeyPatch) -> None:
    original_model = os.environ.get("DEEPSEEK_MODEL_AI")
    monkeypatch.delenv("DEEPSEEK_MODEL_AI", raising=False)

    try:
        reloaded = importlib.reload(config)
        assert reloaded.get_model() == "deepseek-flash"
    finally:
        if original_model is None:
            monkeypatch.delenv("DEEPSEEK_MODEL_AI", raising=False)
        else:
            monkeypatch.setenv("DEEPSEEK_MODEL_AI", original_model)
        importlib.reload(config)


def test_deepseek_model_honors_ai_override(monkeypatch: pytest.MonkeyPatch) -> None:
    original_model = os.environ.get("DEEPSEEK_MODEL_AI")
    monkeypatch.setenv("DEEPSEEK_MODEL_AI", "test-model")

    try:
        reloaded = importlib.reload(config)
        assert reloaded.get_model() == "test-model"
    finally:
        if original_model is None:
            monkeypatch.delenv("DEEPSEEK_MODEL_AI", raising=False)
        else:
            monkeypatch.setenv("DEEPSEEK_MODEL_AI", original_model)
        importlib.reload(config)
