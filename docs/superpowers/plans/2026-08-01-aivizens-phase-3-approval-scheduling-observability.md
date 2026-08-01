# AIVIZENS Phase 3 Approval, Scheduling, and Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split content generation from publication and delivery, enforce machine quality gates plus mandatory human approval, and make every daily run observable and recoverable.

**Architecture:** A `DigestInputAdapter` supplies normalized source envelopes to the existing parsers. The 06:45 command creates an `ai_digest_runs` record, produces a candidate brief, evaluates a structured quality report, and ends in `blocked` or `awaiting_approval`. A signed read-only Web preview supports review, the Mac Mini CLI performs an atomic approval, and the 08:00 release command publishes only approved immutable content, creates idempotent deliveries, and sends only when the global send switch is enabled.

**Tech Stack:** Python 3.12+, Protocol/dataclasses, psycopg 3 transactions, Pydantic 2, pytest, Gmail IMAP, DeepSeek, Qwen VL, Supabase/Postgres, Next.js 14, TypeScript, HMAC-SHA-256, Resend, launchd, Feishu.

## Global Constraints

- Human approval is mandatory; no date- or time-based automatic approval exists.
- Generation never sends email. Approval never sends email. Release is the only publication/delivery-creation transition.
- `approved` and `published` content is immutable to generation commands.
- The 08:00 scheduled release does nothing except alert when no approved brief exists.
- A late approval requires an explicit `ai_brief release --date YYYY-MM-DD` command.
- Preview URLs are read-only, HMAC-signed, expire within 15 minutes, and do not expose credentials.
- Model output may select/transform text but may not invent source URLs.
- Resend uses one stable subscriber/date idempotency key; routine operations cannot override it with a suffix.
- `AI_EMAIL_SEND_ENABLED=false` blocks Resend but does not block generation, approval, or archive publication.
- Run records contain safe summaries and source metadata, never Gmail credentials or full raw messages by default.

---

### Task 1: Define the Digest input contract

**Files:**
- Create: `packages/ai-brief/ai_brief/digest/input.py`
- Create: `packages/ai-brief/ai_brief/digest/gmail_input.py`
- Create: `packages/ai-brief/tests/test_digest_input.py`
- Modify: `packages/ai-brief/ai_brief/digest/imap_client.py`
- Modify: `packages/ai-brief/ai_brief/digest/generate.py`

**Interfaces:**

```python
DigestKind = Literal["events", "builder", "research", "engineering", "agent"]

@dataclass(frozen=True)
class DigestEnvelope:
    kind: DigestKind
    message_id: str
    subject: str
    received_at: datetime
    requested_date: date
    matched_date: date | None
    used_fallback: bool
    text: str | None
    html: str | None
    attachments: tuple[Attachment, ...]

class DigestInputAdapter(Protocol):
    def fetch(self, brief_date: date) -> dict[DigestKind, DigestEnvelope | None]: ...
```

- [ ] **Step 1: Write failing contract tests**

Cover all five kinds, missing mail, exact-date match, 40-hour tool-learning fallback, stale mail rejection, attachment preservation, and serialization of metadata without raw bodies.

- [ ] **Step 2: Run the focused tests**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_digest_input.py -q
```

- [ ] **Step 3: Implement `GmailDigestAdapter`**

Map the five subject prefixes in `config.py` to `DigestKind`. Events and builder require exact-date matches; research, engineering, and agent may use the existing 40-hour fallback. Include Gmail Message-ID, subject, received time, match date, and fallback flag.

- [ ] **Step 4: Refactor generation to consume envelopes**

Change `build_digest_modules` to:

```python
async def build_digest_modules(
    brief_date: date,
    digests: Mapping[DigestKind, DigestEnvelope | None],
) -> DigestBundle:
    ...
```

Remove direct `fetch_latest` calls from parser/build functions. Keep Qwen image selection and DeepSeek transforms downstream of the adapter.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_digest_input.py packages/ai-brief/tests -q
git add packages/ai-brief/ai_brief/digest packages/ai-brief/tests/test_digest_input.py
git commit -m "refactor(digest): add input adapter contract"
```

### Task 2: Persist safe run metadata and operational views

**Files:**
- Create: `infra/supabase/migrations/0013_ai_digest_runs.sql`
- Modify: `infra/supabase/all_migrations.sql`
- Modify: `packages/ai-brief/ai_brief/storage.py`
- Create: `packages/ai-brief/tests/test_digest_run_storage.py`

**Interfaces:**
- `start_digest_run(conn, brief_date, source_adapter) -> UUID`.
- `finish_digest_run(conn, run_id, *, status, digest_sources, quality_report, stage, error_summary) -> None`.
- Run status: `running | blocked | awaiting_approval | failed | completed`.
- Views: `ai_subscription_stats`, `ai_daily_operations`, `ai_delivery_stats`, `ai_rating_stats`.

- [ ] **Step 1: Write failing run lifecycle tests**

Assert one invocation gets one UUID, start/finish timestamps are recorded, failures retain `failed_stage`, source metadata excludes `text`, `html`, attachment bytes, usernames, and passwords, and duplicate completion is rejected.

- [ ] **Step 2: Run the tests**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_digest_run_storage.py -q
```

- [ ] **Step 3: Add `ai_digest_runs`**

Create columns for `id`, `brief_date`, `source_adapter`, `status`, `started_at`, `finished_at`, `duration_ms`, `digest_sources jsonb`, `parse_counts jsonb`, `quality_report jsonb`, `failed_stage`, `error_summary`, `created_at`, and `updated_at`. Also add `approved_by text` and `source_run_id uuid REFERENCES ai_digest_runs(id)` to `ai_daily_briefs`. Enable RLS and keep access service-role-only.

- [ ] **Step 4: Add aggregate views**

Views must expose counts/rates only and must not expose subscriber emails, tokens, raw error traces, or message bodies. Confirmation rate uses confirmed divided by all non-test signups with a zero-safe denominator.

- [ ] **Step 5: Implement storage functions, verify, and commit**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_digest_run_storage.py -q
git add infra/supabase packages/ai-brief/ai_brief/storage.py packages/ai-brief/tests/test_digest_run_storage.py
git commit -m "feat(ops): record digest pipeline runs"
```

### Task 3: Implement the quality gate

**Files:**
- Create: `packages/ai-brief/ai_brief/quality.py`
- Create: `packages/ai-brief/tests/test_quality.py`
- Modify: `packages/ai-brief/ai_brief/schema.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class QualityIssue:
    code: str
    message: str
    path: str | None = None

@dataclass(frozen=True)
class QualityReport:
    passed: bool
    blockers: tuple[QualityIssue, ...]
    warnings: tuple[QualityIssue, ...]
    metrics: dict[str, int | float | str | bool]

def validate_brief(
    brief: AiBriefContent,
    digests: Mapping[DigestKind, DigestEnvelope | None],
    *,
    existing_status: BriefStatus | None,
    deepseek_complete: bool,
    qwen_complete: bool,
    now: datetime,
) -> QualityReport: ...
```

- [ ] **Step 1: Encode every approved hard blocker as a failing test**

Test: fewer than three Today AI stories; fewer than three AI Masters stories; fewer than two of research/engineering/agent modules; schema failure; blank subject/editorial/intro; missing critical URLs; non-HTTPS or placeholder links; stale required Digest; incomplete DeepSeek after retry; and existing approved/published row.

- [ ] **Step 2: Encode every approved warning as a test**

Test: exactly one missing tool module; Qwen no-image fallback; 40-hour Digest fallback; filtered non-core item count; summary near limit; and a source domain not present in the known-domain set.

- [ ] **Step 3: Run and observe failure**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_quality.py -q
```

- [ ] **Step 4: Implement deterministic validation**

Return stable error codes, sorted by section/path. Accept the current time as an argument; do not call `datetime.now()` inside individual validators. Treat `#`, `javascript:`, non-HTTPS URLs, and common placeholder domains/phrases as blockers. Store counts and freshness hours in metrics.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_quality.py -q
git add packages/ai-brief/ai_brief/quality.py packages/ai-brief/ai_brief/schema.py packages/ai-brief/tests/test_quality.py
git commit -m "feat(content): enforce daily brief quality gates"
```

### Task 4: Split generation from approval and release

**Files:**
- Modify: `packages/ai-brief/ai_brief/runner.py`
- Modify: `packages/ai-brief/ai_brief/storage.py`
- Create: `packages/ai-brief/tests/test_workflow.py`
- Modify: `packages/ai-brief/ai_brief/composer.py`

**Interfaces:**

```python
async def generate_for_review(conn, brief_date, adapter) -> GenerationResult: ...
def approve_brief(conn, brief_date, *, approved_by: str) -> TransitionResult: ...
def release_approved(conn, brief_date, *, only_email: str | None = None) -> ReleaseResult: ...
```

- [ ] **Step 1: Write the complete state-machine test first**

Cover:

- `generating → blocked` on failed quality;
- `generating/blocked/awaiting_approval → awaiting_approval` on a passing regeneration;
- `awaiting_approval → approved` only with a passing stored quality report;
- `approved → published` exactly once;
- generation against `approved/published` returns conflict without model calls;
- release against other states creates no delivery;
- an 08:00 no-approved result is nonzero/no-op with an alert;
- late explicit release succeeds after approval.

- [ ] **Step 2: Run the test and observe current direct-delivery behavior**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_workflow.py -q
```

- [ ] **Step 3: Implement generation transaction boundaries**

Create the run row first. Set/lock the daily row as `generating`, ingest and build outside long database locks, validate, then store content/source/report plus `source_run_id` and transition to `blocked` or `awaiting_approval`. On exceptions, roll back partial content, record a safe failed run, and alert.

- [ ] **Step 4: Implement approval and release transitions**

Approval locks the brief and writes `approved_at` plus the `approved_by` local operator identifier added by the Phase 3 migration. Release locks an `approved` brief, renders frozen content for active subscribers, inserts missing deliveries with `ON CONFLICT (subscriber_id, brief_date) DO NOTHING`, then writes `published_at`, `status='published'`, and the linked run status `completed` in the same transaction.

Replace the current delivery upsert that resets existing rows; a sent/failed delivery must never be rewritten by routine release.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_workflow.py packages/ai-brief/tests -q
git add infra/supabase/migrations/0013_ai_digest_runs.sql infra/supabase/all_migrations.sql packages/ai-brief/ai_brief/runner.py packages/ai-brief/ai_brief/storage.py packages/ai-brief/ai_brief/composer.py packages/ai-brief/tests/test_workflow.py
git commit -m "feat(workflow): require approval before release"
```

### Task 5: Add signed read-only previews

**Files:**
- Create: `packages/ai-brief/ai_brief/preview_tokens.py`
- Create: `packages/ai-brief/tests/test_preview_tokens.py`
- Create: `packages/web/lib/preview-token.ts`
- Create: `packages/web/lib/preview-token.test.ts`
- Create: `packages/web/app/preview/[date]/page.tsx`
- Create: `packages/web/app/preview/[date]/preview-page.test.tsx`
- Modify: `.env.example`
- Modify: `packages/web/.env.local.example`

**Interfaces:**
- Signature payload is ASCII `${date}:${expires}`.
- Signature is lowercase hex `HMAC-SHA-256(PREVIEW_SIGNING_SECRET, payload)`.
- URL is `/preview/YYYY-MM-DD?expires=<unix-seconds>&signature=<hex>`.
- Maximum accepted lifetime is 900 seconds and comparison is constant-time.

- [ ] **Step 1: Add shared cross-language test vectors**

Use a fixed test secret/date/expiry and assert Python and TypeScript produce the same signature. Test tampered date, expiry, signature, expired token, excessive lifetime, missing secret, and published/awaiting preview rendering.

- [ ] **Step 2: Run both failing test suites**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_preview_tokens.py -q
npm --workspace @nev/web test -- lib/preview-token.test.ts 'app/preview/[date]/preview-page.test.tsx'
```

- [ ] **Step 3: Implement HMAC helpers**

Python generates URLs for CLI output; TypeScript validates the same payload with `timingSafeEqual`. Reject if `PREVIEW_SIGNING_SECRET` is absent or shorter than 32 bytes in non-test environments.

- [ ] **Step 4: Implement the read-only preview page**

Validate signature before querying content. Permit `blocked`, `awaiting_approval`, `approved`, and `published`; show status, blockers, warnings, source metadata, and the same `DailyBrief` renderer as the public route. Add `noindex, nofollow`, `Cache-Control: private, no-store`, and no Server Actions.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_preview_tokens.py -q
npm --workspace @nev/web test -- lib/preview-token.test.ts 'app/preview/[date]/preview-page.test.tsx'
git add packages/ai-brief packages/web/lib/preview-token.ts packages/web/lib/preview-token.test.ts packages/web/app/preview .env.example packages/web/.env.local.example
git commit -m "feat(review): add signed daily brief previews"
```

### Task 6: Replace the monolithic CLI with operational commands

**Files:**
- Modify: `packages/ai-brief/ai_brief/cli.py`
- Modify: `packages/ai-brief/ai_brief/__main__.py`
- Create: `packages/ai-brief/tests/test_cli_workflow.py`
- Create: `packages/ai-brief/ai_brief/stats.py`
- Create: `packages/ai-brief/tests/test_stats.py`

**Interfaces:**

```text
ai_brief generate --date YYYY-MM-DD
ai_brief preview-url --date YYYY-MM-DD [--ttl-minutes 15]
ai_brief approve --date YYYY-MM-DD
ai_brief release --date YYYY-MM-DD [--only-email ADDRESS]
ai_brief deliver [--date YYYY-MM-DD] [--retry-transient]
ai_brief stats [--date YYYY-MM-DD] [--json]
```

- [ ] **Step 1: Write failing CLI tests**

Patch adapters/transports and assert exit codes, required arguments, no-approved behavior, blocked approval refusal, stable JSON output, absence of emails/tokens/secrets in stats, and correct explicit late-release behavior.

- [ ] **Step 2: Run the tests**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_cli_workflow.py packages/ai-brief/tests/test_stats.py -q
```

- [ ] **Step 3: Implement commands**

`approve` derives `approved_by` from `AIVIZENS_OPERATOR_ID` and fails if missing. `stats --json` prints subscription counts/rate, brief/run state, digest anomalies, delivery counts/retries, and rating distribution. Human output uses the same data object.

`deliver --retry-transient` first calls a storage function that moves only explicitly classified transient failures below the retry ceiling back to `pending`; it never resets permanent failures or sent rows.

- [ ] **Step 4: Remove direct-send semantics**

Remove or hard-deprecate `daily`; it must not execute generation plus delivery. Keep `compose` only as a local file preview helper if tests require it. Ensure `generate`, `approve`, and `preview-url` never import or call `send_pending`.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_cli_workflow.py packages/ai-brief/tests/test_stats.py -q
uv run python -m ai_brief --help
git add packages/ai-brief/ai_brief packages/ai-brief/tests
git commit -m "feat(cli): add review and release operations"
```

### Task 7: Harden delivery and recovery

**Files:**
- Modify: `packages/ai-brief/ai_brief/deliverer.py`
- Modify: `packages/ai-brief/ai_brief/resend_client.py`
- Modify: `packages/ai-brief/ai_brief/config.py`
- Create: `packages/ai-brief/tests/test_delivery_safety.py`
- Modify: `packages/ai-brief/ai_brief/templates/ai_brief.html.j2`
- Modify: `packages/ai-brief/ai_brief/templates/ai_brief.txt.j2`

**Interfaces:**
- Idempotency key is permanently `aivizens-{brief_date}-{subscriber_id}`.
- `send_pending(conn, *, brief_date=None, retry_transient=False)` honors `AI_EMAIL_SEND_ENABLED`.
- Only classified transient failures can return to `pending` through explicit retry.

- [ ] **Step 1: Write failing delivery safety tests**

Cover the global switch, active subscriber check at claim time, stable key, one-click unsubscribe headers, no idempotency suffix, separate commits, transient/permanent classification, bounded retries, and link targets for confirmation-based rating/unsubscribe pages.

- [ ] **Step 2: Run the tests**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_delivery_safety.py -q
```

- [ ] **Step 3: Implement safe claim and send behavior**

Join `ai_subscribers` with `status='active'` when claiming. When sending is disabled, do not claim rows. Remove `AI_IDEMPOTENCY_SUFFIX`. Sanitize error summaries before storage/logging and never log recipient email at INFO level.

- [ ] **Step 4: Validate rendered email contracts**

Check HTML/text body parity, mobile width, all source links, confirmation-based rating links, ordinary unsubscribe page, RFC 8058 headers, sender identity, and absence of NEV labels.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_delivery_safety.py -q
git add packages/ai-brief/ai_brief
git commit -m "fix(delivery): make AIVIZENS sends recoverable"
```

### Task 8: Split Mac Mini scheduling and alerting

**Files:**
- Rename: `ops/launchd/com.aivizens.ai-daily.plist` → `ops/launchd/com.aivizens.ai-generate.plist`
- Create: `ops/launchd/com.aivizens.ai-release.plist`
- Rename: `ops/launchd/run-ai-daily.sh` → `ops/launchd/run-ai-generate.sh`
- Create: `ops/launchd/run-ai-release.sh`
- Modify: `ops/launchd/install-ai-daily.sh`
- Modify: `ops/launchd/README.md`
- Create: `ops/launchd/test-schedules.sh`
- Create: `docs/runbooks/daily-operations.md`

**Interfaces:**
- `com.aivizens.ai-generate` runs at 06:45 Asia/Shanghai.
- `com.aivizens.ai-release` runs at 08:00 Asia/Shanghai.
- Both scripts use the explicit `PROJECT_ROOT`, `uv`, dated logs, and nonzero exit propagation.

- [ ] **Step 1: Write a static schedule test**

Create a shell test using `plutil -lint` and `/usr/libexec/PlistBuddy` to assert labels, script paths, 06:45, 08:00, distinct log files, and absence of the `daily` CLI command.

- [ ] **Step 2: Run it against the existing single schedule**

```bash
bash ops/launchd/test-schedules.sh
```

Expected before implementation: missing generate/release plist failures.

- [ ] **Step 3: Implement separate scripts and plists**

Generate runs `uv run python -m ai_brief generate --date "$(TZ=Asia/Shanghai date +%F)"`. Release runs the matching explicit date. Scripts use `set -euo pipefail`, locate `uv`, write safe logs, and send a Feishu P1 on failure. The install script bootouts only exact legacy AIVIZENS label targets, installs both new labels, and prints their resolved schedules.

- [ ] **Step 4: Document the human approval window**

Runbook sequence: check 06:45 run → obtain preview URL → inspect in Codex/browser as desired → run `approve` → check `stats` → let 08:00 release run. Include blocked recovery, no-approval, late release, email kill switch, transient retry, and log locations.

- [ ] **Step 5: Verify and commit**

```bash
bash ops/launchd/test-schedules.sh
make verify
git add ops/launchd docs/runbooks/daily-operations.md
git commit -m "ops: split AIVIZENS generation and release schedules"
```

### Task 9: Complete shadow and test-recipient acceptance

**Files:**
- Create: `docs/runbooks/phase-3-acceptance.md`
- Create: `ops/smoke/verify-ai-workflow.sh`
- Modify: `.gitignore`

- [ ] **Step 1: Add a safe workflow smoke script**

The script accepts `--date`, queries only counts/statuses, asserts the brief moves through expected states, and refuses to run against a production database unless `--production-read-only` is supplied. It never prints content, email addresses, or credentials.

- [ ] **Step 2: Perform one no-send shadow run**

```bash
AIVIZENS_RUN_DATE="$(TZ=Asia/Shanghai date +%F)"
AI_EMAIL_SEND_ENABLED=false uv run python -m ai_brief generate --date "$AIVIZENS_RUN_DATE"
uv run python -m ai_brief preview-url --date "$AIVIZENS_RUN_DATE"
uv run python -m ai_brief approve --date "$AIVIZENS_RUN_DATE"
AI_EMAIL_SEND_ENABLED=false uv run python -m ai_brief release --date "$AIVIZENS_RUN_DATE"
uv run python -m ai_brief stats --date "$AIVIZENS_RUN_DATE" --json
```

Record run ID, states, warning/blocker counts, and delivery count only in the acceptance document.

- [ ] **Step 3: Perform one test-recipient E2E**

Use an isolated test subscriber and explicit `--only-email`. Confirm the confirmation email, welcome email, daily email, source links, rating POST, unsubscribe POST, Resend ID, and idempotent second release. Do not use the production subscriber list.

- [ ] **Step 4: Run the phase gate and commit evidence**

```bash
make verify
bash ops/launchd/test-schedules.sh
AIVIZENS_RUN_DATE="$(TZ=Asia/Shanghai date +%F)"
bash ops/smoke/verify-ai-workflow.sh --date "$AIVIZENS_RUN_DATE"
git add docs/runbooks/phase-3-acceptance.md ops/smoke/verify-ai-workflow.sh .gitignore
git commit -m "test(ops): verify approved publication workflow"
```

## Phase 3 Gate

The gate passes only when:

- all deterministic verification commands pass;
- a no-send shadow run completes;
- one explicit test-recipient E2E completes;
- an unapproved and a blocked brief are both proven unable to publish or send;
- a repeated release/delivery creates no duplicate email;
- both launchd plists validate at 06:45 and 08:00.

Do not start NEV retirement until this evidence is recorded.
