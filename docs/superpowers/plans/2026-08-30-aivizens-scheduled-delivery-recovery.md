# AIVIZENS Scheduled Delivery Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a transient Gmail IMAP or PostgreSQL connection loss from leaving a daily AIVIZENS brief permanently generating and unpublished.

**Architecture:** Keep the existing `generate → approve → release` workflow and its single Resend delivery path. Retry only one transient IMAP connection failure per digest fetch. If the workflow connection has died while recording a pipeline failure, create one fresh database connection solely to persist the failed state; a later scheduled generation can then reclaim the blocked row.

**Tech Stack:** Python 3.12, psycopg, imaplib, pytest, launchd shell runners.

**Spec:** `docs/superpowers/plans/2026-08-27-aivizens-site-daily-automation-fixes.md`

## Global Constraints

- Do not create a second mail-delivery mechanism.
- Keep generation, approval, release, and delivery as explicit workflow stages.
- Do not log email bodies, credentials, tokens, or raw provider errors.
- The scheduler must fail closed: no release or delivery when generation is not approved.

---

### Task 1: Retry a transient IMAP connection failure

**Files:**
- Modify: `packages/ai-brief/ai_brief/digest/imap_client.py`
- Test: `packages/ai-brief/tests/test_imap_parse.py`

**Interfaces:**
- Consumes: `fetch_latest(sender, subject_prefix, date_str, ...)`
- Produces: the existing `DigestEmail | None` result after at most two connection attempts.

- [ ] **Step 1: Write the failing test**

```python
def test_fetch_latest_retries_one_imap_abort_then_returns_email() -> None:
    fake = _FakeIMAP([...])
    with patch.object(imap_client, "_connect", side_effect=[imaplib.IMAP4.abort("EOF"), fake]):
        assert fetch_latest(...) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/ai-brief/tests/test_imap_parse.py::test_fetch_latest_retries_one_imap_abort_then_returns_email -q`

Expected: `IMAP4.abort` escapes because `fetch_latest` has no retry.

- [ ] **Step 3: Write minimal implementation**

```python
for attempt in range(2):
    try:
        return _fetch_latest_once(...)
    except (imaplib.IMAP4.abort, OSError):
        if attempt == 1:
            raise
        log.warning("ai_imap.retrying_connection", attempt=attempt + 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/ai-brief/tests/test_imap_parse.py -q`

Expected: all IMAP parser tests pass.

### Task 2: Persist pipeline failure using a fresh connection when necessary

**Files:**
- Modify: `packages/ai-brief/ai_brief/runner.py`
- Test: `packages/ai-brief/tests/test_workflow.py`

**Interfaces:**
- Consumes: the existing run ID and brief ownership (`brief_date`, `run_id`).
- Produces: a durable `blocked` brief and `failed` run, or a P1 alert if both the original and replacement connections are unavailable.

- [ ] **Step 1: Write the failing test**

```python
async def test_generation_reconnects_to_record_failure_after_connection_loss() -> None:
    original = _connection()
    replacement = _connection()
    with patch.object(storage, "mark_brief_generation_failed", side_effect=[psycopg.OperationalError("lost"), None]), \
         patch.object(runner, "connect", return_value=replacement):
        result = await runner.generate_for_review(original, BRIEF_DATE, failing_adapter)
    assert result.status == "failed"
    assert replacement.commit.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/ai-brief/tests/test_workflow.py::test_generation_reconnects_to_record_failure_after_connection_loss -q`

Expected: the original failure-recording exception is re-raised and no replacement connection is used.

- [ ] **Step 3: Write minimal implementation**

```python
def _record_generation_failure(...):
    try:
        _write_failure(conn, ...)
    except Exception:
        recovered = connect()
        _write_failure(recovered, ...)
        recovered.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/ai-brief/tests/test_workflow.py -q`

Expected: all workflow tests pass.

### Task 3: Verify scheduler contract and recover the interrupted 2026-08-30 run

**Files:**
- Modify: `ops/launchd/test-schedules.sh`
- Modify: `ops/launchd/run-ai-generate.sh` only if its current contract test exposes a real missing invariant.

**Interfaces:**
- Consumes: `com.aivizens.ai-generate` at 06:45 and `com.aivizens.ai-release` at 08:00.
- Produces: a tested scheduler contract and a one-time, operator-authorized recovery of the interrupted brief.

- [ ] **Step 1: Add a failing scheduler contract check**

```bash
grep -q 'AI_EMAIL_SEND_ENABLED' "$GEN_RUN"
```

- [ ] **Step 2: Run it to verify failure**

Run: `bash ops/launchd/test-schedules.sh`

Expected: the new contract fails before the runner is changed.

- [ ] **Step 3: Implement only the required runner invariant**

```bash
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a; source "$PROJECT_ROOT/.env"; set +a
fi
```

- [ ] **Step 4: Verify source and runtime separately**

Run: `bash ops/launchd/test-schedules.sh`, targeted pytest suites, `ruff`, `mypy`, and a no-send live IMAP/database preflight.

Expected: tests pass and all five required dated digests are visible without sending mail.

- [ ] **Step 5: Recover and backfill**

After tests and live preflight pass, mark only the orphaned 2026-08-30 generating row as failed, generate that date, approve only a passing report, release, and deliver only still-pending rows.
