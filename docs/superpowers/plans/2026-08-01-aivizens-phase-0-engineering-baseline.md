# AIVIZENS Phase 0 Engineering Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish deterministic install, test, lint, type-check, build, and CI commands before product behavior changes.

**Architecture:** Force all Python test entrypoints through the root pytest configuration and importlib collection mode, add a real Vitest harness for the Next.js workspace, and make one `make verify` command mirror CI. Resolve existing lint violations with narrow configuration exceptions only for tests and long prompt literals.

**Tech Stack:** uv, Python 3.12+, pytest, Ruff, mypy, npm workspaces, Vitest, jsdom, TypeScript, Next.js 14, GitHub Actions.

## Global Constraints

- Do not change runtime product behavior in this phase.
- Do not delete NEV code or data in this phase.
- Python integration/network/golden/perf tests remain opt-in.
- CI and local commands must use the same configuration and file scope.
- Never print `.env` values or production credentials in verification output.

---

### Task 1: Make Python test discovery deterministic

**Files:**
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Modify: `.github/workflows/test.yml`
- Modify: `packages/delivery/tests/integration/test_sender_e2e.py`
- Test: `packages/ai-brief/tests/test_schema.py`
- Test: `tests/`

**Interfaces:**
- Consumes: root `pyproject.toml` pytest markers.
- Produces: `make test-unit` and `make test-integration` commands used by CI and later phase gates.

- [ ] **Step 1: Add a failing collection check**

Run the current command and save its failure in the task notes:

```bash
uv run pytest packages/ -q --collect-only
```

Expected before the fix: collection errors such as `No module named 'tests.test_config'`.

- [ ] **Step 2: Mark the delivery E2E correctly**

Add immediately after imports in `packages/delivery/tests/integration/test_sender_e2e.py`:

```python
pytestmark = pytest.mark.integration
```

- [ ] **Step 3: Force the root pytest configuration and import mode**

Set root pytest options to:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "--import-mode=importlib -m 'not network and not integration and not perf and not golden'"
```

Replace the Make targets with:

```make
test-unit:
	uv run pytest -c pyproject.toml packages tests -q

test-integration:
	uv run pytest -c pyproject.toml packages tests -m integration -q
```

- [ ] **Step 4: Verify collection and unit execution**

Run:

```bash
make test-unit
```

Expected: no collection errors; unit tests pass; integration/network/golden/perf tests are deselected.

- [ ] **Step 5: Align GitHub Actions and commit**

Change the unit workflow command to `make test-unit` and the integration workflow command to `make test-integration`.

```bash
git add pyproject.toml Makefile .github/workflows/test.yml packages/delivery/tests/integration/test_sender_e2e.py
git commit -m "test: make Python test discovery deterministic"
```

### Task 2: Add a working Web unit-test harness

**Files:**
- Modify: `package.json`
- Modify: `packages/web/package.json`
- Create: `packages/web/vitest.config.ts`
- Create: `packages/web/test/setup.ts`
- Create: `packages/web/lib/subscribers.test.ts`
- Modify: `package-lock.json`

**Interfaces:**
- Consumes: the `@/` TypeScript path alias from `packages/web/tsconfig.json`.
- Produces: `npm test` and `npm --workspace @nev/web test`.

- [ ] **Step 1: Write a failing smoke test**

Create `packages/web/lib/subscribers.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parseProduct, productLabel } from "./subscribers";

describe("subscriber helpers", () => {
  it("maps AI product labels", () => {
    expect(parseProduct("ai")).toBe("ai");
    expect(productLabel("ai")).toBe("AIVIZENS · AI 趋势");
  });
});
```

- [ ] **Step 2: Run it to verify the harness is missing**

Run:

```bash
npm test
```

Expected before the fix: `vitest: command not found`.

- [ ] **Step 3: Install and configure Vitest**

Add workspace dev dependencies `vitest`, `jsdom`, `@testing-library/react`, and `@testing-library/jest-dom`. Add:

```ts
// packages/web/vitest.config.ts
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: { "@": path.resolve(__dirname, ".") } },
  test: {
    environment: "jsdom",
    setupFiles: ["./test/setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
  },
});
```

```ts
// packages/web/test/setup.ts
import "@testing-library/jest-dom/vitest";
```

Set scripts:

```json
{
  "scripts": {
    "test": "npm --workspace @nev/web test"
  }
}
```

```json
{
  "scripts": {
    "test": "vitest run --config vitest.config.ts"
  }
}
```

- [ ] **Step 4: Run the Web test**

Run:

```bash
npm test
```

Expected: one passing test file.

- [ ] **Step 5: Commit**

```bash
git add package.json package-lock.json packages/web/package.json packages/web/vitest.config.ts packages/web/test/setup.ts packages/web/lib/subscribers.test.ts
git commit -m "test(web): add Vitest baseline"
```

### Task 3: Establish a passing lint and type-check baseline

**Files:**
- Modify: `pyproject.toml`
- Modify: Python files reported by `uv run ruff check packages/`
- Modify: `.github/workflows/lint.yml`
- Modify: `packages/web/package.json`

**Interfaces:**
- Produces: `make lint` and `make typecheck`, both exiting 0.

- [ ] **Step 1: Record current failures**

Run:

```bash
uv run ruff check packages/
uv run mypy packages/ai-brief packages/shared
npm --workspace @nev/web run lint
npm --workspace @nev/web run typecheck
```

Expected before the fix: Ruff reports existing violations; the Web typecheck passes.

- [ ] **Step 2: Narrow rules only where the signal is known to be noise**

Add:

```toml
[tool.ruff.lint.per-file-ignores]
"**/tests/**/*.py" = ["ANN", "S101"]
"packages/ai-brief/ai_brief/digest/condenser.py" = ["E501"]
```

Do not globally disable `F`, `B`, `S`, or `BLE` rules for runtime code.

- [ ] **Step 3: Apply safe fixes and resolve remaining runtime errors**

Run:

```bash
uv run ruff check packages/ --fix
uv run ruff check packages/
```

Manually fix remaining runtime findings such as unused imports, overly broad exceptions without justification, missing annotations, and unsafe template warnings with scoped `# noqa` comments only where the text template intentionally disables HTML escaping.

- [ ] **Step 4: Define stable Make and CI commands**

Add:

```make
lint:
	uv run ruff check packages/
	npm --workspace @nev/web run lint

typecheck:
	uv run mypy packages/ai-brief packages/shared
	npm --workspace @nev/web run typecheck
```

Update `.github/workflows/lint.yml` to run `make lint` and `make typecheck`.

- [ ] **Step 5: Verify and commit**

```bash
make lint
make typecheck
git add pyproject.toml Makefile .github/workflows/lint.yml packages
git commit -m "chore: establish lint and typecheck baseline"
```

### Task 4: Add a single local/CI verification command

**Files:**
- Modify: `Makefile`
- Modify: `package.json`
- Modify: `.github/workflows/test.yml`
- Create: `docs/runbooks/local-development.md`

**Interfaces:**
- Consumes: `make test-unit`, `make lint`, `make typecheck`, and the Web build.
- Produces: `make verify`, the mandatory gate for every later task.

- [ ] **Step 1: Add the orchestration target**

```make
.PHONY: verify

verify: test-unit lint typecheck
	npm --workspace @nev/web run build
```

- [ ] **Step 2: Document clean-room setup**

Create `docs/runbooks/local-development.md` with the exact sequence:

```bash
uv sync --frozen
npm ci
cp .env.example .env
cp packages/web/.env.local.example packages/web/.env.local
make verify
```

Document that real secrets must never be committed and that normal tests use dummy environment values from CI.

- [ ] **Step 3: Make CI invoke the same gate**

Use `make verify` in the non-integration CI job after `uv sync --frozen` and `npm ci`.

- [ ] **Step 4: Run the clean verification**

Run:

```bash
make verify
```

Expected: all unit tests, lint, type checks, and Next.js production build pass.

- [ ] **Step 5: Commit**

```bash
git add Makefile package.json .github/workflows/test.yml docs/runbooks/local-development.md
git commit -m "ci: add unified verification gate"
```

### Task 5: Audit dependency and environment contracts

**Files:**
- Modify: `.env.example`
- Modify: `packages/web/.env.local.example`
- Create: `docs/runbooks/production-inventory.md`
- Modify: `package-lock.json`
- Modify: `uv.lock`

**Interfaces:**
- Produces: an environment-key inventory without secret values and reproducible lockfiles.

- [ ] **Step 1: Compare code reads against example keys**

Run:

```bash
rg -o 'os\.environ\.get\("[A-Z0-9_]+|process\.env\.[A-Z0-9_]+' packages ops | sort -u
```

Expected: a key-name-only list; no values.

- [ ] **Step 2: Update example files with key names and purpose**

Ensure the examples contain at least:

```dotenv
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=
DEEPSEEK_API_KEY=
QWEN_API_KEY=
RESEND_API_KEY=
RESEND_FROM_EMAIL_AI=aivizens.daily@aivizens.com
AI_GMAIL_IMAP_USER=
AI_GMAIL_IMAP_PASSWORD=
AI_IMAP_PROXY=
FEISHU_WEBHOOK_URL=
TURNSTILE_SECRET_KEY=
NEXT_PUBLIC_TURNSTILE_SITE_KEY=
WEB_BASE_URL=https://aivizens.com
```

- [ ] **Step 3: Create a production inventory without credentials**

Document ownership and location—not values—for Vercel project, Supabase project, Resend domain, Gmail account, Feishu webhook, Mac Mini repository path, launchd labels, log directory, and emergency contact procedure.

- [ ] **Step 4: Refresh lockfiles conservatively and verify audits**

Run:

```bash
uv lock --check
npm audit --omit=dev
npm audit fix --package-lock-only
make verify
```

If a production high-severity advisory remains, update only the affected direct dependency within the current major version and rerun `make verify`.

- [ ] **Step 5: Commit**

```bash
git add .env.example packages/web/.env.local.example docs/runbooks/production-inventory.md package-lock.json uv.lock
git commit -m "docs: define production environment contract"
```

## Phase 0 Gate

Run:

```bash
make verify
git status --short
```

Expected: verification exits 0 and the worktree contains only intentional committed changes. Do not start Phase 1 until this gate passes.
