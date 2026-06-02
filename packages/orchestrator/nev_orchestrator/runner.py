"""Daily pipeline runner: 7 steps, each independent subprocess.

Failure policy per step:
- 'continue' — log + 飞书 alert + 继续下一步
- 'abort'    — log + 飞书 alert + 中断 pipeline

完全成功 → 发一次 INFO 总结到飞书。
"""
from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from nev_shared.feishu import AlertLevel, send_alert
from nev_shared.logger import get_logger

log = get_logger("orchestrator.runner")

FailurePolicy = Literal["continue", "abort"]


@dataclass(frozen=True)
class Step:
    name: str
    cmd: list[str]
    failure: FailurePolicy
    alert_level: AlertLevel


@dataclass
class DailyResult:
    brief_date: date
    started_at: float = field(default_factory=time.time)
    succeeded_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    aborted: bool = False

    @property
    def success(self) -> bool:
        return not self.failed_steps and not self.aborted

    @property
    def duration_seconds(self) -> float:
        return time.time() - self.started_at


def _build_steps(brief_date: date) -> list[Step]:
    date_str = brief_date.isoformat()
    return [
        Step(
            name="sync",
            cmd=[sys.executable, "-m", "nev_crawler.source_loader", "sync"],
            failure="continue",
            alert_level=AlertLevel.P2,
        ),
        Step(
            name="crawl",
            cmd=[sys.executable, "-m", "nev_crawler", "run", "--window", "24"],
            failure="continue",
            alert_level=AlertLevel.P1,
        ),
        Step(
            name="pipeline",
            cmd=[sys.executable, "-m", "nev_pipeline", "run"],
            failure="abort",
            alert_level=AlertLevel.P0,
        ),
        Step(
            name="summarize",
            cmd=[sys.executable, "-m", "nev_summarizer", "run", "--date", date_str],
            failure="abort",
            alert_level=AlertLevel.P0,
        ),
        Step(
            name="sales",
            cmd=[sys.executable, "-m", "nev_summarizer", "sales-extract",
                 "--month", date_str[:7]],
            failure="continue",
            alert_level=AlertLevel.P2,
        ),
        Step(
            name="compose",
            cmd=[sys.executable, "-m", "nev_composer", "run", "--date", date_str],
            failure="abort",
            alert_level=AlertLevel.P0,
        ),
        Step(
            name="deliver",
            cmd=[sys.executable, "-m", "nev_delivery", "send"],
            failure="abort",
            alert_level=AlertLevel.P0,
        ),
    ]


def _run_step(step: Step, dry_run: bool) -> tuple[bool, str, str]:
    if dry_run:
        log.info("step.dry_run", name=step.name, cmd=" ".join(step.cmd))
        return True, "[dry-run]", ""

    log.info("step.start", name=step.name, cmd=" ".join(step.cmd))
    started = time.time()
    try:
        proc = subprocess.run(
            step.cmd,
            capture_output=True,
            text=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - started
        log.error("step.timeout", name=step.name, elapsed_s=elapsed)
        return False, "", f"timeout after {elapsed:.0f}s"

    elapsed = time.time() - started
    ok = proc.returncode == 0
    log.info(
        "step.done",
        name=step.name,
        ok=ok,
        returncode=proc.returncode,
        elapsed_s=round(elapsed, 1),
    )
    return ok, proc.stdout or "", proc.stderr or ""


def run_daily(
    *,
    brief_date: date,
    dry_run: bool = False,
    resume: str | None = None,
) -> DailyResult:
    """执行一日完整 pipeline。"""
    result = DailyResult(brief_date=brief_date)
    steps = _build_steps(brief_date)

    if resume:
        idx = next((i for i, s in enumerate(steps) if s.name == resume), -1)
        if idx < 0:
            raise ValueError(
                f"unknown resume step '{resume}'; "
                f"valid: {[s.name for s in steps]}"
            )
        log.info("runner.resume_from", step=resume)
        steps = steps[idx:]

    for step in steps:
        ok, stdout, stderr = _run_step(step, dry_run)
        if ok:
            result.succeeded_steps.append(step.name)
            continue

        result.failed_steps.append(step.name)
        body = (
            f"Step: {step.name}\n"
            f"Date: {brief_date.isoformat()}\n"
            f"Stderr (tail 500 chars):\n{stderr[-500:] if stderr else '(empty)'}"
        )
        send_alert(
            level=step.alert_level,
            title=f"NEV 早报 daily pipeline 失败：{step.name}",
            body=body,
        )

        if step.failure == "abort":
            result.aborted = True
            log.error("runner.aborted", step=step.name)
            break

    if result.success and not dry_run:
        send_alert(
            level=AlertLevel.INFO,
            title=f"NEV 早报 {brief_date.isoformat()} 完成",
            body=(
                f"耗时 {result.duration_seconds:.0f}s\n"
                f"成功步骤：{', '.join(result.succeeded_steps)}"
            ),
        )

    return result
