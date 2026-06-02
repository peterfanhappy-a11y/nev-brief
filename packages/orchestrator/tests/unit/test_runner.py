"""Runner unit tests — mock subprocess + feishu.send_alert."""
from __future__ import annotations

import subprocess
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from nev_orchestrator.runner import DailyResult, Step, run_daily


def _ok_proc() -> MagicMock:
    p = MagicMock(spec=subprocess.CompletedProcess)
    p.returncode = 0
    p.stdout = "OK"
    p.stderr = ""
    return p


def _fail_proc(stderr: str = "ERROR") -> MagicMock:
    p = MagicMock(spec=subprocess.CompletedProcess)
    p.returncode = 1
    p.stdout = ""
    p.stderr = stderr
    return p


def test_run_daily_all_success_returns_all_ok():
    """7 steps all OK → DailyResult.failed_steps == []."""
    with patch("nev_orchestrator.runner.subprocess.run", return_value=_ok_proc()), \
         patch("nev_orchestrator.runner.send_alert") as alert:
        result = run_daily(brief_date=date(2026, 6, 1))
    assert result.failed_steps == []
    assert result.success
    info_calls = [c for c in alert.call_args_list if c.kwargs.get("level").value == "INFO"]
    assert len(info_calls) == 1
    assert "完成" in info_calls[0].kwargs["title"]


def test_run_daily_crawl_failure_continues_to_pipeline():
    """crawl 失败 → 飞书告警 + 继续 pipeline (continue policy)."""
    def fake_run(cmd, **kwargs):
        joined = " ".join(cmd)
        if "nev_crawler" in joined and "source_loader" not in joined:
            return _fail_proc("network error")
        return _ok_proc()

    with patch("nev_orchestrator.runner.subprocess.run", side_effect=fake_run), \
         patch("nev_orchestrator.runner.send_alert") as alert:
        result = run_daily(brief_date=date(2026, 6, 1))
    assert "crawl" in result.failed_steps
    p1_calls = [c for c in alert.call_args_list if c.kwargs.get("level").value == "P1"]
    assert len(p1_calls) >= 1


def test_run_daily_pipeline_failure_aborts():
    """pipeline 失败 → abort policy → 后续步骤不执行."""
    def fake_run(cmd, **kwargs):
        joined = " ".join(cmd)
        if "nev_pipeline" in joined:
            return _fail_proc("DB lock")
        return _ok_proc()

    with patch("nev_orchestrator.runner.subprocess.run", side_effect=fake_run), \
         patch("nev_orchestrator.runner.send_alert") as alert:
        result = run_daily(brief_date=date(2026, 6, 1))
    assert "pipeline" in result.failed_steps
    assert result.aborted
    assert "summarize" not in result.succeeded_steps
    assert "deliver" not in result.succeeded_steps
    p0_calls = [c for c in alert.call_args_list if c.kwargs.get("level").value == "P0"]
    assert len(p0_calls) >= 1


def test_run_daily_dry_run_skips_subprocess():
    """dry_run=True → 只打印步骤，不调 subprocess."""
    with patch("nev_orchestrator.runner.subprocess.run") as run_mock, \
         patch("nev_orchestrator.runner.send_alert"):
        result = run_daily(brief_date=date(2026, 6, 1), dry_run=True)
    run_mock.assert_not_called()
    assert result.success


def test_run_daily_resume_from_step():
    """resume='compose' → 跳过 sync/crawl/pipeline/summarize/sales，从 compose 开始."""
    called_cmds: list[str] = []
    def fake_run(cmd, **kwargs):
        called_cmds.append(" ".join(cmd))
        return _ok_proc()

    with patch("nev_orchestrator.runner.subprocess.run", side_effect=fake_run), \
         patch("nev_orchestrator.runner.send_alert"):
        result = run_daily(brief_date=date(2026, 6, 1), resume="compose")
    assert any("nev_composer" in c for c in called_cmds)
    assert any("nev_delivery" in c for c in called_cmds)
    assert not any("nev_crawler" in c for c in called_cmds)
    assert not any("nev_pipeline" in c for c in called_cmds)
    assert not any("nev_summarizer" in c for c in called_cmds)


def test_step_command_includes_brief_date():
    """compose step 应该把 --date 参数传进去."""
    captured = {}
    def fake_run(cmd, **kwargs):
        if "nev_composer" in " ".join(cmd):
            captured["compose_cmd"] = cmd
        return _ok_proc()

    with patch("nev_orchestrator.runner.subprocess.run", side_effect=fake_run), \
         patch("nev_orchestrator.runner.send_alert"):
        run_daily(brief_date=date(2026, 6, 1))
    assert "--date" in captured["compose_cmd"]
    assert "2026-06-01" in captured["compose_cmd"]
