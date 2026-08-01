# AIVIZENS Phase 4 NEV Retirement and Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the legacy NEV product from code, routes, jobs, documentation, and production data only after AIVIZENS dependencies are isolated and the NEV SQL backup passes a restore drill.

**Architecture:** First rename the still-useful shared runtime to `aivizens_shared`, move the two AI dependencies out of NEV packages, and prove the AI suite runs without legacy imports. Then replace old Web routes with explicit 410 handling and delete legacy packages/tests/jobs/docs. Finally create a plain-SQL backup containing the public schema plus the eight NEV tables' data, verify it in an isolated database, and apply a dedicated retirement migration that preserves every `ai_*` object and `touch_updated_at()`.

**Tech Stack:** Python/uv, Next.js middleware, Vitest/Playwright, Postgres `pg_dump`/`psql`, Supabase, shell safety checks, Git.

## Global Constraints

- Do not delete any NEV production data until the backup hash, per-table counts, sample checks, and isolated restore all pass.
- Resolve and display the exact production project/host/database before any mutation; compare it with `EXPECTED_SUPABASE_PROJECT_REF`.
- Backup files live in a user-selected restricted directory outside Git; never place dumps in the repository.
- Preserve `touch_updated_at()` because AIVIZENS tables use it.
- Preserve every `ai_*` table, row, policy, trigger, function, view, and storage object.
- Historical migrations remain immutable; retirement is migration `0014_retire_nev.sql`.
- Old NEV page/API/management routes return 410, not 301/302/404.
- The approved AIVIZENS trust bar, logos, and empty social links remain unchanged.
- All repository file edits/deletions use `apply_patch`; never use broad recursive delete commands.
- A production mutation step requires the user-approved intent plus fresh exact-target checks at execution time.

---

### Task 1: Rename the shared runtime to AIVIZENS

**Files:**
- Create: `packages/shared/aivizens_shared/__init__.py`
- Move via `apply_patch`: `packages/shared/nev_shared/{config,db,feishu,logger,net,retry}.py` → `packages/shared/aivizens_shared/`
- Delete via `apply_patch`: `packages/shared/nev_shared/`
- Modify: `packages/shared/pyproject.toml`
- Modify: `packages/shared/tests/**/*.py`
- Modify: `packages/ai-brief/ai_brief/**/*.py`
- Modify: `packages/ai-brief/tests/**/*.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Distribution: `aivizens-shared`.
- Import root: `aivizens_shared`.
- Public helpers retain existing call signatures during the rename.

- [ ] **Step 1: Add an import-contract test**

Create/modify a shared test that imports `aivizens_shared.config`, `.db`, `.feishu`, `.logger`, `.net`, and `.retry`. Add an assertion that importing `nev_shared` fails after migration.

- [ ] **Step 2: Run the test and observe the missing package**

```bash
uv run pytest -c pyproject.toml packages/shared/tests -q
```

- [ ] **Step 3: Move modules and update imports**

Use `apply_patch` for every tracked move/delete. Rename distribution metadata and remove the unused `nev-contracts` dependency from shared. Replace imports in AIVIZENS code/tests only; do not repair legacy packages that will be deleted.

- [ ] **Step 4: Refresh the workspace lock and scan**

```bash
uv lock
rg -n "nev_shared|nev-contracts" packages/shared packages/ai-brief pyproject.toml
```

Expected: no matches in AIVIZENS/shared paths.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest -c pyproject.toml packages/shared packages/ai-brief -q
git add packages/shared packages/ai-brief pyproject.toml uv.lock
git commit -m "refactor: rename shared runtime for AIVIZENS"
```

### Task 2: Move the remaining AI helpers out of NEV packages

**Files:**
- Create: `packages/shared/aivizens_shared/llm.py`
- Create: `packages/shared/tests/test_llm.py`
- Create: `packages/ai-brief/ai_brief/crawler/robots.py`
- Create: `packages/ai-brief/tests/test_robots.py`
- Modify: `packages/ai-brief/ai_brief/{selector,summarizer}.py`
- Modify: `packages/ai-brief/ai_brief/digest/condenser.py`
- Modify: `packages/ai-brief/ai_brief/crawler/runner.py`
- Modify: `packages/ai-brief/pyproject.toml`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- `aivizens_shared.llm.extract_json_with_retry(...) -> dict[str, Any] | None` keeps the current caller contract.
- `ai_brief.crawler.robots.RobotsChecker` defaults to the AIVIZENS crawler user agent from configuration.

- [ ] **Step 1: Copy behavior into failing contract tests**

Port only tests needed by AI: DeepSeek JSON success/parse failure/transient retry/auth failure and robots allow/disallow/404/network behavior. Add import assertions against the new modules.

- [ ] **Step 2: Run and observe missing modules**

```bash
uv run pytest -c pyproject.toml packages/shared/tests/test_llm.py packages/ai-brief/tests/test_robots.py -q
```

- [ ] **Step 3: Implement AIVIZENS-owned helpers**

Move the tested behavior, update logging names/user agent, and update AIVIZENS imports. Add direct `openai` and required HTTP dependencies to the owning package manifests.

- [ ] **Step 4: Remove manifest dependencies**

Remove `nev-contracts` and `nev-crawler` from `packages/ai-brief/pyproject.toml`; remove all legacy distributions from root runtime dependencies and workspace sources only after Task 3 deletions are prepared.

- [ ] **Step 5: Verify dependency isolation and commit**

```bash
rg -n "nev_pipeline|nev_crawler|nev_contracts|nev-shared|nev-crawler|nev-pipeline" packages/ai-brief packages/shared
uv run pytest -c pyproject.toml packages/shared packages/ai-brief -q
git add packages/shared packages/ai-brief pyproject.toml uv.lock
git commit -m "refactor: isolate AIVIZENS from NEV helpers"
```

Expected `rg`: no output.

### Task 3: Delete legacy Python and TypeScript workspaces

**Files:**
- Delete via `apply_patch`: `packages/contracts/`
- Delete via `apply_patch`: `packages/crawler/`
- Delete via `apply_patch`: `packages/pipeline/`
- Delete via `apply_patch`: `packages/summarizer/`
- Delete via `apply_patch`: `packages/composer/`
- Delete via `apply_patch`: `packages/delivery/`
- Delete via `apply_patch`: `packages/orchestrator/`
- Delete via `apply_patch`: `tests/composer/`, `tests/crawler/`, `tests/pipeline/`, `tests/summarizer/`, and NEV-only `tests/integration/`
- Modify: `pyproject.toml`
- Modify: `package.json`
- Modify: `packages/web/package.json`
- Modify: `Makefile`
- Modify: `.github/workflows/test.yml`
- Modify: `.github/workflows/lint.yml`
- Modify: `uv.lock`
- Modify: `package-lock.json`

**Interfaces:**
- Root Python project: `aivizens` with workspaces `packages/shared` and `packages/ai-brief` only.
- Web workspace name: `@aivizens/web`.
- Verification commands target AIVIZENS/shared tests only.

- [ ] **Step 1: Record the exact tracked deletion set**

```bash
git ls-files packages/contracts packages/crawler packages/pipeline packages/summarizer packages/composer packages/delivery packages/orchestrator tests | sort
```

Review the list and retain any AI-owned test fixture by moving it with `apply_patch` before deletion.

- [ ] **Step 2: Update manifests before deletion**

Set root description/name to AIVIZENS, retain only `aivizens-shared` and `ai-brief`, remove the TypeScript contracts workspace, rename the Web workspace, and update every `npm --workspace` command.

- [ ] **Step 3: Delete tracked legacy files with `apply_patch`**

Delete only the exact directories listed above. Do not delete `packages/ai-brief`, `packages/shared`, `packages/web`, `infra`, or any untracked user file.

- [ ] **Step 4: Refresh locks and scan imports**

```bash
uv lock
npm install --package-lock-only
rg -n "nev_(contracts|crawler|pipeline|summarizer|composer|delivery|orchestrator)|@nev/" --glob '!docs/superpowers/**' .
```

Expected: no runtime, test, manifest, or workflow matches.

- [ ] **Step 5: Verify and commit**

```bash
make verify
git add pyproject.toml package.json packages Makefile .github uv.lock package-lock.json tests
git commit -m "refactor: remove legacy NEV workspaces"
```

### Task 4: Return HTTP 410 for every retired NEV entrypoint

**Files:**
- Create: `packages/web/middleware.ts`
- Create: `packages/web/middleware.test.ts`
- Delete via `apply_patch`: `packages/web/app/nev/`
- Delete via `apply_patch`: `packages/web/app/api/nev/`
- Delete via `apply_patch`: `packages/web/app/manage/`
- Delete via `apply_patch`: `packages/web/app/api/preferences/`
- Modify: `packages/web/app/api/unsubscribe/route.ts`
- Modify: `packages/web/lib/subscribers.ts`
- Modify: `packages/web/app/sitemap.ts`
- Create: `packages/web/e2e/nev-gone.spec.ts`

**Interfaces:**
- 410 paths: `/nev`, `/nev/:path*`, `/api/nev/:path*`, `/manage`, and `/api/preferences`.
- `product=nev` on shared compatibility endpoints returns 410.
- 410 response has `X-Robots-Tag: noindex` and no `Location` header.

- [ ] **Step 1: Write failing middleware/API tests**

Cover every route family plus query variants. Assert status 410, no redirect header, no database call, and no sitemap entry. Assert AIVIZENS `/`, `/daily/*`, `/confirm`, `/unsubscribe`, `/rate`, and `/api/ai/*` are not intercepted.

- [ ] **Step 2: Run the focused tests**

```bash
npm --workspace @aivizens/web test -- middleware.test.ts
```

- [ ] **Step 3: Implement exact middleware matching**

Return a small plain-text `410 Gone` response for retired routes. Do not use a catch-all that can shadow AIVIZENS paths. Remove product-table abstraction from AIVIZENS code after compatibility tests pass.

- [ ] **Step 4: Delete NEV pages/APIs and add browser checks**

The E2E test requests representative old index, dated, item, subscribe, manage, and preferences URLs and asserts 410/no redirect.

- [ ] **Step 5: Verify and commit**

```bash
npm --workspace @aivizens/web test -- middleware.test.ts
npm --workspace @aivizens/web run test:e2e -- nev-gone.spec.ts
npm --workspace @aivizens/web run build
git add packages/web
git commit -m "feat(web): retire NEV routes with HTTP 410"
```

### Task 5: Remove NEV jobs and obsolete documentation

**Files:**
- Delete via `apply_patch`: `ops/launchd/com.nev.daily.plist`
- Delete via `apply_patch`: `ops/launchd/install-daily.sh`
- Delete via `apply_patch`: `ops/launchd/run-daily.sh`
- Delete via `apply_patch`: `ops/windows/`
- Delete via `apply_patch`: `docs/agent-6-first-delivery.md`
- Delete via `apply_patch`: `docs/agent-7-first-daily-run.md`
- Modify: `README.md`
- Modify: `ops/launchd/README.md`
- Modify: `.env.example`
- Modify: `docs/runbooks/production-inventory.md`

- [ ] **Step 1: Rewrite the repository overview**

Document AIVIZENS only: purpose, architecture, local setup, double opt-in, daily workflow, public archive, verification, deployments, and runbook links. Remove NEV feature/status/setup claims.

- [ ] **Step 2: Remove obsolete jobs/docs with `apply_patch`**

Keep the Phase 3 AIVIZENS generate/release jobs. Remove NEV variables from examples only when no AIVIZENS code reads them.

- [ ] **Step 3: Scan current product surfaces**

```bash
rg -n "NEV|新能源|nev-brief|com\.nev|/nev" README.md ops .env.example packages --glob '!docs/superpowers/**'
```

Review every remaining match. Allow only historical migration comments or explicit 410 compatibility tests; remove all current-product claims.

- [ ] **Step 4: Verify and commit**

```bash
make verify
bash ops/launchd/test-schedules.sh
git add README.md ops docs/agent-6-first-delivery.md docs/agent-7-first-daily-run.md .env.example docs/runbooks/production-inventory.md
git commit -m "docs: remove retired NEV operations"
```

### Task 6: Build restore-tested NEV backup tooling

**Files:**
- Create: `ops/backup/backup-nev.sh`
- Create: `ops/backup/verify-nev-backup.sh`
- Create: `ops/backup/nev-tables.txt`
- Create: `ops/backup/test-backup-safety.sh`
- Create: `docs/runbooks/nev-retirement.md`
- Modify: `.gitignore`

**Interfaces:**
- Exact tables: `subscribers`, `subscriber_preferences`, `sources`, `articles_raw`, `articles_processed`, `daily_briefs`, `vehicle_sales_daily`, `deliveries`.
- Required environment: `PGSERVICE=aivizens-production`, `AIVIZENS_RESTORE_PGSERVICE=aivizens-nev-restore`, `EXPECTED_SUPABASE_PROJECT_REF`, `AIVIZENS_BACKUP_DIR`.
- Output: timestamped plain SQL, SHA-256 file, JSON manifest of source counts, and restore-verification JSON.

- [ ] **Step 1: Write safety tests first**

The shell test must prove the scripts refuse: missing variables, a backup path inside the repository, world-readable output, source project-ref mismatch, restore service equal to source service, and any table list containing `ai_`.

- [ ] **Step 2: Implement the backup script**

Resolve the source host/database with `psql` read-only queries and compare project ref. Create the backup directory with mode 700 and files with mode 600. Produce one plain SQL file by combining a `public` schema-only dump with data-only dumps for the eight explicit tables, using `--no-owner --no-privileges`. Record source counts and selected non-sensitive primary-key/date samples in the manifest. Never print the connection URL.

- [ ] **Step 3: Implement isolated restore verification**

Require an explicit `AIVIZENS_RESTORE_PGSERVICE` whose normalized host/database differ from source. The verification script targets a disposable local PostgreSQL database, bootstraps the `pgcrypto` extension plus `anon`, `authenticated`, and `service_role` roles required by the schema dump, restores with `ON_ERROR_STOP`, compares all eight counts and samples, verifies constraints/indexes, and writes a verification record containing the backup SHA and timestamp. Verify restored `ai_*` row counts are zero because no AI data is included.

- [ ] **Step 4: Run locally against disposable databases**

```bash
bash ops/backup/test-backup-safety.sh
AIVIZENS_BACKUP_DIR='/Users/jack/Documents/AI日报项目/backups/nev-retirement' bash ops/backup/backup-nev.sh
AIVIZENS_BACKUP_SQL="$(find '/Users/jack/Documents/AI日报项目/backups/nev-retirement' -name 'nev-*.sql' -type f -print | sort | tail -n 1)"
AIVIZENS_RESTORE_PGSERVICE=aivizens-nev-restore bash ops/backup/verify-nev-backup.sh "$AIVIZENS_BACKUP_SQL"
```

- [ ] **Step 5: Commit tooling, never dumps**

```bash
git status --short
git add ops/backup docs/runbooks/nev-retirement.md .gitignore
git commit -m "ops: add restore-tested NEV backup workflow"
```

### Task 7: Add and test the retirement migration

**Files:**
- Create: `infra/supabase/migrations/0014_retire_nev.sql`
- Modify: `infra/supabase/all_migrations.sql`
- Create: `infra/supabase/tests/test_retire_nev.sql`
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Migration drops exactly the eight NEV tables.
- Migration retains `touch_updated_at()` and every `ai_*` object.

- [ ] **Step 1: Write the SQL acceptance test**

Before migration, seed one row in representative NEV and AI tables. After migration, assert `to_regclass` is null for all eight NEV tables, non-null for all `ai_*` tables, AI counts are unchanged, `touch_updated_at()` exists, and an AI row update still fires its trigger.

- [ ] **Step 2: Implement the explicit migration**

Use one transaction and explicit dependency order:

```sql
DROP TABLE deliveries;
DROP TABLE subscriber_preferences;
DROP TABLE articles_processed;
DROP TABLE articles_raw;
DROP TABLE sources;
DROP TABLE daily_briefs;
DROP TABLE vehicle_sales_daily;
DROP TABLE subscribers;
```

Do not use `CASCADE`; unexpected dependencies must abort the migration for review.

- [ ] **Step 3: Verify against a fresh local database**

```bash
docker compose -f infra/docker-compose.yml up -d postgres
for f in infra/supabase/migrations/*.sql; do PGPASSWORD=nev_local_dev psql -v ON_ERROR_STOP=1 -h localhost -p 54322 -U nev -d nev_brief -f "$f"; done
PGPASSWORD=nev_local_dev psql -v ON_ERROR_STOP=1 -h localhost -p 54322 -U nev -d nev_brief -f infra/supabase/tests/test_retire_nev.sql
```

- [ ] **Step 4: Verify and commit**

```bash
make verify
git add infra/supabase .github/workflows/test.yml
git commit -m "chore(db): retire legacy NEV schema"
```

### Task 8: Execute the authorized production NEV retirement

**Files:**
- Modify with non-secret evidence: `docs/runbooks/nev-retirement.md`

- [ ] **Step 1: Resolve the exact target read-only**

Run key-name/host/database/project-ref checks, migration-version queries, the eight NEV counts, and all `ai_*` counts. Stop if the host/project does not match the inventory or if an unexpected dependent object exists.

- [ ] **Step 2: Apply the additive AIVIZENS migrations**

Through the established migration tracking mechanism, apply any not-yet-applied migrations 0011–0013 in order. Do not rerun an already-applied file. Verify the new subscription columns/RPC, brief workflow columns, run table, views, and AI trigger behavior before deploying code that depends on them.

- [ ] **Step 3: Deploy the Phase 4 cutover with both switches disabled**

Deploy the exact verified Phase 4 commit to the connected Vercel project with `SUBSCRIPTIONS_ENABLED=false`; keep `AI_EMAIL_SEND_ENABLED=false` on the Mac Mini. Smoke-test AIVIZENS homepage/archive and verify representative NEV page/API/management URLs return 410 without redirects before deleting data.

- [ ] **Step 4: Produce and restore-test the final backup**

Run `backup-nev.sh`, verify its SHA, restore it into an isolated empty database, and compare every count/sample. Record only backup filename, SHA, timestamp, project ref, counts, and verification result in the runbook; never commit the SQL dump or connection details.

- [ ] **Step 5: Capture the pre-mutation AI invariant snapshot**

Record counts for `ai_subscribers`, `ai_articles`, `ai_daily_briefs`, `ai_deliveries`, `ai_ratings`, `ai_digest_runs`, storage images, and the shared trigger function identity.

- [ ] **Step 6: Apply migration `0014` to the verified production target**

Use `psql -v ON_ERROR_STOP=1` or the established Supabase migration mechanism against the exact resolved target. Do not paste credentials into the command history or logs.

- [ ] **Step 7: Verify production invariants and route behavior**

Confirm all eight NEV tables are absent, AI counts match the pre-mutation snapshot, AI trigger updates work, `make verify` remains green, and deployed representative NEV URLs return 410 without redirects.

- [ ] **Step 8: Commit non-secret evidence**

```bash
git add docs/runbooks/nev-retirement.md
git commit -m "docs: record verified NEV retirement"
```

## Phase 4 Gate

The gate passes only when the repository has no active NEV package, test, page, API, job, or product documentation; old routes return 410; the external SQL backup has a matching successful restore record; production NEV tables are gone; and all AIVIZENS data/invariants remain unchanged. Do not clear AIVIZENS subscribers or open public signup until Phase 5.
