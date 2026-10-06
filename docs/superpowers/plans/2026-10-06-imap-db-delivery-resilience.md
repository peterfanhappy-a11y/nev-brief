# AIVIZENS IMAP, Generation, and Delivery Resilience Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development to implement this plan task-by-task.

**Goal:** Prevent date-specific digest ingestion from scanning historical mail, prevent slow external work from invalidating the generation database connection, and make interrupted delivery safely recoverable without broad duplicate sends.

**Architecture:** Narrow IMAP server searches before fetching message headers while retaining client-side validation and unpadded-date compatibility. Split generation into short database transactions around external Gmail/model/image work. Claim deliveries one at a time and recover only recent stale `sending` rows while their stable Resend idempotency keys remain inside the documented 24-hour window.

**Tech Stack:** Python 3.12+, imaplib, psycopg, Resend SDK, pytest.

## Global Constraints

- Preserve current digest sender, subject-prefix, exact-subject, freshness, and zero-padded/unpadded date compatibility.
- Never trust IMAP search alone; keep client-side sender/subject/date and precise INTERNALDATE validation.
- Do not hold or reuse a database connection across Gmail, model, image processing, or object-storage calls.
- Keep each database transaction short and preserve the existing durable run/brief status model.
- Claim at most one delivery at a time so one crash can strand at most one row.
- Automatic recovery applies only when `retry_transient=True`, after 15 minutes, and before the stable idempotency key is 24 hours old.
- Never automatically requeue `sending` rows older than 24 hours; they require operator reconciliation.
- No Hermes changes, production data changes, subscriber broadcast, push, merge, or deployment belong in this plan.

## Review Focus

- IMAP servers may return the same UID for multiple date variants; deduplicate before fetching.
- Date search must cover mixed zero-padding without reopening a prefix-wide historical scan.
- A caller-owned connection may remain valid for its original transaction but must not be reused after external work.
- Generation persistence must use a fresh connection and close it in success and failure paths.
- Recovery boundaries at exactly 15 minutes and 24 hours must be deterministic.
- A send accepted by Resend followed by a database failure must retry with the same idempotency key, while rows outside the safe window stay untouched.

---

### Task 1: Narrow IMAP Candidate Searches

**Files:**
- Modify: `packages/ai-brief/ai_brief/digest/imap_client.py`
- Modify: `packages/ai-brief/tests/test_imap_parse.py`

**Interfaces:**
- Consumes: existing `fetch_latest` arguments and client-side validation.
- Produces: bounded IMAP search criteria and deduplicated candidate UIDs.

- [ ] Write RED tests proving unrelated historical dates are not fetched, date variants remain compatible, duplicate UID results are fetched once, and no-date fallback uses `SINCE` plus precise INTERNALDATE filtering.
- [ ] Run the selected IMAP tests and confirm failure is caused by the broad prefix search.
- [ ] Implement the smallest server-side query builder and UID deduplication that satisfies the tests.
- [ ] Run `packages/ai-brief/tests/test_imap_parse.py` GREEN.
- [ ] Commit Task 1.

### Task 2: Persist Generated Briefs Through Fresh Connections

**Files:**
- Modify: `packages/ai-brief/ai_brief/runner.py`
- Modify: `packages/ai-brief/tests/test_workflow.py`

**Interfaces:**
- Consumes: existing `generate_for_review` public signature and storage functions.
- Produces: a fresh short-lived persistence connection after external content work.

- [ ] Write a RED workflow test where the caller connection becomes unusable during external work but a fresh connection persists the candidate and completes the run.
- [ ] Run the selected workflow test and confirm the original connection is currently reused.
- [ ] Implement fresh-connection persistence without changing generation/release semantics.
- [ ] Run focused workflow tests GREEN.
- [ ] Commit Task 2.

### Task 3: Recover Recent Stuck Deliveries and Claim One at a Time

**Files:**
- Modify: `packages/ai-brief/ai_brief/storage.py`
- Modify: `packages/ai-brief/ai_brief/deliverer.py`
- Modify: `packages/ai-brief/tests/test_storage.py`
- Modify: `packages/ai-brief/tests/test_deliverer.py`
- Modify: `packages/ai-brief/tests/test_delivery_safety.py`

**Interfaces:**
- Consumes: stable delivery idempotency key and `retry_transient` operator switch.
- Produces: `recover_recent_sending_deliveries` and one-at-a-time claiming.

- [ ] Write RED tests for the 15-minute and 24-hour recovery boundaries, explicit retry gating, one-at-a-time claiming, and same-key recovery after a post-send database failure.
- [ ] Run the selected storage/delivery tests and confirm the missing recovery/batch-claim behavior.
- [ ] Implement minimal storage recovery and delivery loop changes.
- [ ] Run selected storage/delivery tests GREEN.
- [ ] Commit Task 3.

### Final Verification

- [ ] Run all `packages/ai-brief` unit tests.
- [ ] Run Ruff and strict mypy for `packages/ai-brief`.
- [ ] Run the repository `make verify` gate and report any unrelated baseline failure by name.
- [ ] Review the whole branch against this plan, fix all Critical/Important findings with RED-to-GREEN tests, and leave no unreported decisions.
