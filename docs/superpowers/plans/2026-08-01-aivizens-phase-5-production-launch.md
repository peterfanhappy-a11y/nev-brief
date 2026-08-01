# AIVIZENS Phase 5 Production Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy AIVIZENS to production, intentionally reset the AI subscriber list, open double-opt-in signup, install the two Mac Mini schedules, and verify the first production publication/delivery cycle.

**Architecture:** Launch is controlled by two independent switches: the Web subscription switch and the Python email-send switch. Production is deployed with signup and sending disabled, verified in that safe state, then the approved one-time subscriber reset is executed. After a test-address double-opt-in and test-recipient delivery pass, signup opens, schedules are installed, and email sending is enabled for the first human-approved issue.

**Tech Stack:** Git/GitHub, Vercel, Supabase/Postgres, Resend, Cloudflare Turnstile, Gmail IMAP, Mac Mini launchd, curl/dig, Feishu, shell smoke scripts.

## Global Constraints

- Exact target resolution precedes every production database, Vercel, Resend, and launchd mutation.
- Never print or commit secret values; environment verification reports key names/presence only.
- Production initially deploys with `SUBSCRIPTIONS_ENABLED=false` and `AI_EMAIL_SEND_ENABLED=false`.
- Clear `ai_subscribers`, `ai_deliveries`, and `ai_ratings` exactly once; preserve `ai_articles`, `ai_daily_briefs`, `ai_digest_runs`, and images.
- Signup opens only after double-opt-in, confirmation, unsubscribe, rating, archive, 410, and test-recipient flows pass on production.
- Human approval remains mandatory after launch.
- “100,000+ readers”, company logos, and `href="#"` social entries remain as explicitly approved.
- Do not recreate NEV tables, routes, jobs, or redirects during rollback; restore NEV only by an explicit new user decision using the verified backup.

---

### Task 1: Add production preflight and smoke tooling

**Files:**
- Create: `ops/launch/preflight.sh`
- Create: `ops/launch/production-smoke.sh`
- Create: `ops/launch/reset-ai-subscribers.sql`
- Create: `ops/launch/test-launch-safety.sh`
- Create: `docs/runbooks/production-launch.md`
- Modify: `.gitignore`

**Interfaces:**
- Required identifiers: `EXPECTED_GIT_REMOTE`, `EXPECTED_VERCEL_PROJECT`, `EXPECTED_SUPABASE_PROJECT_REF`, `EXPECTED_PRODUCTION_DOMAIN`.
- Smoke target defaults to no host; production host must be passed explicitly as `--base-url https://aivizens.com`.
- Reset SQL truncates exactly `ai_ratings`, `ai_deliveries`, and `ai_subscribers` in one statement/transaction.

- [ ] **Step 1: Write safety tests first**

Prove preflight refuses a dirty tree, wrong remote, wrong branch, wrong Vercel project, wrong Supabase project ref, unresolved/mismatched domain, missing required environment-key names, enabled production switches during initial deployment, and any reset SQL mentioning `ai_articles`, `ai_daily_briefs`, `ai_digest_runs`, or storage.

- [ ] **Step 2: Implement the key-name-only preflight**

Check:

- Git remote `https://github.com/peterfanhappy-a11y/nev-brief.git`, branch, commit, tag status, and clean tree;
- `make verify` result;
- Vercel project/domain and presence of all required Production env keys;
- Supabase host/project ref and migrations 0011–0014 by schema assertions;
- Resend sender/domain configuration without printing API responses containing sensitive data;
- DNS/HTTPS for `aivizens.com`;
- Gmail IMAP key presence and read-only adapter health;
- launchd labels and current loaded state;
- `SUBSCRIPTIONS_ENABLED=false` and `AI_EMAIL_SEND_ENABLED=false` for the initial deploy.

- [ ] **Step 3: Implement the reset SQL with invariants**

Use:

```sql
BEGIN;
TRUNCATE TABLE ai_ratings, ai_deliveries, ai_subscribers;
COMMIT;
```

The wrapper records before/after counts and aborts unless the exact project-ref check passes. It also snapshots preserved-table counts before and verifies them after.

- [ ] **Step 4: Implement read-only smoke checks**

Test `/` 200, a known published `/daily/YYYY-MM-DD` 200, an unpublished date 404, representative NEV URLs 410/no redirect, sitemap AIVIZENS-only, robots exclusions, security headers, and public form state. Add an optional `--mutating-test-email` path used only after explicit target confirmation.

- [ ] **Step 5: Verify and commit**

```bash
bash ops/launch/test-launch-safety.sh
make verify
git add ops/launch docs/runbooks/production-launch.md .gitignore
git commit -m "ops: add guarded production launch workflow"
```

### Task 2: Freeze and publish the release candidate

**Files:**
- Modify with results: `docs/runbooks/production-launch.md`

- [ ] **Step 1: Review repository and phase evidence**

Confirm Phase 0–4 gates, restore-tested NEV backup SHA, production NEV retirement evidence, no open P0/P1 issue, no placeholders, and a clean `make verify` run.

- [ ] **Step 2: Run the production preflight**

```bash
bash ops/launch/preflight.sh
```

Stop on any mismatch. Resolve configuration; do not weaken assertions.

- [ ] **Step 3: Create the release commit/tag locally**

```bash
git status --short
git tag -a aivizens-v1.0.0 -m "AIVIZENS production launch"
git show --stat --oneline aivizens-v1.0.0
```

- [ ] **Step 4: Push the exact verified commit and tag**

```bash
git push origin main
git push origin aivizens-v1.0.0
```

Record the immutable commit SHA and CI URL/result.

- [ ] **Step 5: Wait for CI and record the gate**

Use GitHub checks to require unit tests, lint, typecheck, build, migration test, and static schedule tests to pass before deployment.

### Task 3: Deploy production with signup and sending disabled

**Files:**
- Modify with deployment ID: `docs/runbooks/production-launch.md`

- [ ] **Step 1: Verify production environment key presence**

Required keys include Supabase, Resend, Turnstile, `WEB_BASE_URL=https://aivizens.com`, `PREVIEW_SIGNING_SECRET`, `SUBSCRIPTION_HASH_SECRET`, and `SUBSCRIPTIONS_ENABLED=false`. Verify values through masked/hashed comparison only.

- [ ] **Step 2: Deploy the tagged commit**

Use the established connected Vercel project. If the repository is Git-connected, promote the deployment built from the recorded commit; otherwise run:

```bash
npx vercel deploy --prod --yes
```

Record deployment ID, commit SHA, project, and domain.

- [ ] **Step 3: Run safe production smoke tests**

```bash
bash ops/launch/production-smoke.sh --base-url https://aivizens.com
```

Expected: site/archive work, NEV returns 410, subscription UI says temporarily unavailable, and no API request can create a subscriber while the switch is off.

- [ ] **Step 4: Verify rollback target**

Record the immediately previous Vercel deployment ID and confirm it can be promoted without database rollback. Do not perform the rollback unless a gate fails.

### Task 4: Execute the authorized AI subscriber reset

**Files:**
- Modify with non-secret counts: `docs/runbooks/production-launch.md`

- [ ] **Step 1: Re-resolve the Supabase target**

Run the preflight project-ref/host/database checks again and query counts for all `ai_*` tables and storage objects. Verify signup and email sending remain disabled.

- [ ] **Step 2: Record the intentional deletion scope**

Display counts for `ai_subscribers`, `ai_deliveries`, and `ai_ratings`. Confirm the SQL contains no wildcard, `CASCADE`, or preserved table name.

- [ ] **Step 3: Run the single transaction**

Use a preconfigured `PGSERVICE=aivizens-production` or equivalent process environment and run:

```bash
psql -v ON_ERROR_STOP=1 --file=ops/launch/reset-ai-subscribers.sql
```

Do not put a connection URL or password in the command line, process listing, shell history, or logs.

- [ ] **Step 4: Verify preserved data and empty subscriber state**

Assert the three reset tables contain zero rows and that pre/post counts for `ai_articles`, `ai_daily_briefs`, `ai_digest_runs`, and images are identical. Run `ai_brief stats --json` and record only aggregate output.

- [ ] **Step 5: Record recoverability**

State that this one-time subscriber reset is intentional and not restored during normal rollback. NEV backup remains separately recoverable.

### Task 5: Validate production double opt-in with one controlled address

**Files:**
- Modify with pass/fail evidence: `docs/runbooks/production-launch.md`

- [ ] **Step 1: Enable signup while keeping delivery disabled**

Set `SUBSCRIPTIONS_ENABLED=true` in Vercel Production, redeploy/promote the same release commit, and verify `AI_EMAIL_SEND_ENABLED=false` remains on the Mac Mini.

- [ ] **Step 2: Execute the controlled browser/API flow**

Run the mutating smoke test with one explicitly designated test address: valid Turnstile → uniform 202 → `pending_confirmation` → confirmation POST → `active` → welcome email. Verify raw token absence in the database/logs.

- [ ] **Step 3: Verify scanner-safe actions**

Open confirmation/unsubscribe/rating links with GET and confirm no mutation. Then explicitly POST unsubscribe and verify state/timestamp; resubscribe and reconfirm. Test RFC 8058 POST independently.

- [ ] **Step 4: Verify abuse controls**

Use only the test address/IP to hit documented limits, observe HTTP 429 and `Retry-After`, then verify rollover/recovery. Do not run broad load tests against production.

- [ ] **Step 5: Leave the controlled address active**

This becomes the sole recipient for the first production release test. Verify aggregate subscriber count is exactly one.

### Task 6: Install and validate Mac Mini schedules

**Files:**
- Modify with loaded labels: `docs/runbooks/production-launch.md`

- [ ] **Step 1: Resolve the exact Mac Mini project and environment**

Confirm repository absolute path, release commit SHA, `.env` permissions, required key presence, timezone, `uv` path, log directory permissions, and no loaded `com.nev.*` labels.

- [ ] **Step 2: Install AIVIZENS schedules**

```bash
bash ops/launchd/install-ai-daily.sh
```

Verify loaded labels are exactly `com.aivizens.ai-generate` and `com.aivizens.ai-release`, with 06:45 and 08:00 calendar intervals.

- [ ] **Step 3: Run generate manually with email disabled**

```bash
AI_EMAIL_SEND_ENABLED=false uv run python -m ai_brief generate --date "$(TZ=Asia/Shanghai date +%F)"
uv run python -m ai_brief stats --date "$(TZ=Asia/Shanghai date +%F)" --json
```

Verify `blocked` or `awaiting_approval` behavior and Feishu alert delivery.

- [ ] **Step 4: Validate logs and retry instructions**

Confirm logs contain run IDs/stages but no email addresses, message bodies, tokens, passwords, or API keys. Exercise only a simulated transient failure and documented retry.

### Task 7: Complete the first approved production issue

**Files:**
- Modify with aggregate evidence: `docs/runbooks/production-launch.md`

- [ ] **Step 1: Review a passing production candidate**

Generate at/after 06:45, confirm `awaiting_approval`, create a 15-minute preview URL, inspect full content/source links/images/warnings, and refuse approval if any blocker exists.

- [ ] **Step 2: Approve through the Mac Mini CLI**

```bash
AIVIZENS_RUN_DATE="$(TZ=Asia/Shanghai date +%F)"
uv run python -m ai_brief approve --date "$AIVIZENS_RUN_DATE"
uv run python -m ai_brief stats --date "$AIVIZENS_RUN_DATE" --json
```

Verify status `approved`, actor/timestamp present, and content hash unchanged from preview.

- [ ] **Step 3: Enable sending for the controlled first release**

Set `AI_EMAIL_SEND_ENABLED=true` only after approval. At 08:00 allow the scheduled release, or use explicit `release` if testing after 08:00.

- [ ] **Step 4: Verify publication and delivery**

Confirm status `published`, archive 200, homepage/sitemap inclusion, exactly one delivery, one Resend ID, correct sender/list-unsubscribe headers, full HTML/text content, and no duplicate on a second release/deliver invocation.

- [ ] **Step 5: Exercise feedback and unsubscribe**

With the controlled address, submit one rating and confirm aggregate stats, then validate unsubscribe and reconfirm if the address should remain for ongoing operations.

### Task 8: Open and hand off daily operations

**Files:**
- Modify: `docs/runbooks/production-launch.md`
- Modify: `docs/runbooks/daily-operations.md`
- Modify: `README.md`

- [ ] **Step 1: Confirm public launch state**

Signup enabled, sending enabled, two launchd jobs loaded, one published issue visible, no P0/P1 alert, stats healthy, NEV routes 410, and all secrets masked.

- [ ] **Step 2: Run final smoke and verification**

```bash
make verify
bash ops/launch/production-smoke.sh --base-url https://aivizens.com
uv run python -m ai_brief stats --date "$(TZ=Asia/Shanghai date +%F)" --json
```

- [ ] **Step 3: Document the daily operator checklist**

Keep the mandatory sequence: 06:45 alert/run review → signed preview → CLI approval → pre-08:00 stats check → 08:00 publish/send → post-send aggregate check. Include late release, blocked issue, kill switches, delivery retry, Vercel rollback, and escalation paths.

- [ ] **Step 4: Record deferred scope**

Create follow-up notes for `HermesMarkdownAdapter`, dual-read comparison, and Hermes Agent result evaluation. Do not implement them in this launch.

- [ ] **Step 5: Commit launch evidence and operating docs**

```bash
git add docs/runbooks/production-launch.md docs/runbooks/daily-operations.md README.md
git commit -m "docs: hand off AIVIZENS production operations"
git push origin main
```

## Phase 5 Completion Gate

AIVIZENS is launched only when all of the following are true:

- `https://aivizens.com` serves the verified release and real published content;
- double opt-in is open and unconfirmed addresses cannot receive email;
- production subscribers started from the approved empty state;
- 06:45 generation, human approval, and 08:00 release are operational;
- the first production issue is published and delivered exactly once;
- scanner-safe confirmation, unsubscribe, and rating flows pass;
- NEV surfaces remain 410 and NEV data remains absent;
- CI, smoke tests, stats, Feishu alerts, and rollback references are green;
- daily operations remain human-approved until the user explicitly authorizes another policy.
