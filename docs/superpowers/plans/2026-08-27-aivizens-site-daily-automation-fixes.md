# AIVIZENS 日报体验与自动发布 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 AIVIZENS 订阅与日报展示体验，统一邮件/网站内容规则，回填并发送 2026-08-27 日报，并让 Mac mini 在质量通过时自动审批、发布和发送每日简报。

**Architecture:** 保留现有 Supabase、Resend、Peter Gmail IMAP 和 Next.js/Vercel 架构。前端继续使用已有订阅 API 与 Turnstile；日报内容在 Python digest 生成层完成过滤、数量和结构化格式，Jinja 邮件模板与 React 网站组件分别渲染同一冻结内容；launchd 以 06:45 generate → 质量通过自动 approve → 08:00 release/deliver 的顺序运行，任何失败都 fail-closed。

**Tech Stack:** Next.js 15, React, TypeScript, Vitest, Playwright, Python 3.12, Pydantic, pytest, Jinja2, Supabase/PostgreSQL, Resend, macOS launchd。

**Spec:** `docs/superpowers/specs/2026-08-01-aivizens-production-launch-design.md`

## Global Constraints

- 保持邮箱确认、Turnstile、Supabase RLS 和 Resend 投递链路；不以关闭验证换取订阅成功。
- Peter Gmail (`peter.fan.happy@gmail.com`) 仍是 digest 输入源；Hermes Markdown 读取不纳入本次改动。
- Agent 工具只保留非 `openai/codex`、非 `anthropic/claude`、非 `google/gemini` 仓库，并展示 3 条。
- 今日 AI、AI 大神、Agent 工具的序号从 1 开始；AI 工程字段使用“序号. 字段：”并让字段值另起一行。
- 自动流程仅在 `generate` 返回质量通过且日报状态为 `awaiting_approval` 时执行 approve；blocked/failed/conflict 不发布、不发送。
- 发送总开关读取项目根 `.env` 的 `AI_EMAIL_SEND_ENABLED=true`；任何密钥不进入 Git。
- 所有生产写操作必须先读取目标状态，操作后读取数据库状态和公开 URL 验证；不重复发送已有 `sent` delivery。
- 明天的目标时间使用 `Asia/Shanghai`：06:45 生成/自动审批，08:00 发布并发送。

---

### Task 1: 打开生产订阅入口并保留安全验证

**Files:**
- Modify: `packages/web/lib/feature-flags.ts`
- Modify: `packages/web/components/ai-subscribe-form.tsx`（仅在测试证明需要时）
- Test: `packages/web/lib/feature-flags.test.ts`
- Test: `packages/web/components/ai-subscribe-form.test.tsx`

**Interfaces:**
- Consumes: `SUBSCRIPTIONS_ENABLED`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, `/api/ai/subscribe`。
- Produces: 生产首页显示可用订阅表单；未配置 Turnstile 时仍显示明确不可用状态，API 继续返回安全错误而不绕过验证。

- [ ] **Step 1: Write the failing tests**

  Add a test proving the production default/explicit flag exposes the form when the deployment flag is enabled, and an existing test proving an absent Turnstile key never submits to the API.

- [ ] **Step 2: Run tests to verify they fail**

  Run: `npm --workspace @nev/web test -- lib/feature-flags.test.ts components/ai-subscribe-form.test.tsx`
  Expected: the new production-enabled expectation fails against the current disabled flag behavior.

- [ ] **Step 3: Implement the minimal configuration behavior**

  Make the feature flag explicit and deployment-safe: production must receive `SUBSCRIPTIONS_ENABLED=true`; preserve the existing Turnstile guard and API route. Do not add a bypass token or direct insert path.

- [ ] **Step 4: Run focused tests**

  Run the command from Step 2 and confirm all focused tests pass.

- [ ] **Step 5: Verify deployment configuration without exposing values**

  Check Vercel environment names only (`SUBSCRIPTIONS_ENABLED`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`) and set missing non-secret flag values through the deployment configuration. Never print secret values.

- [ ] **Step 6: Commit**

  ```bash
  git add packages/web/lib/feature-flags.ts packages/web/lib/feature-flags.test.ts packages/web/components/ai-subscribe-form.tsx packages/web/components/ai-subscribe-form.test.tsx
  git commit -m "fix(web): enable AI subscription entrypoint"
  ```

### Task 2: 修复品牌 Logo 和最新日报卡片点击区域

**Files:**
- Modify: `packages/web/app/page.tsx`
- Modify: `packages/web/components/latest-briefs-grid.tsx`
- Test: `packages/web/components/latest-briefs-grid.test.tsx`
- Test: `packages/web/app/page.test.tsx`

**Interfaces:**
- Consumes: `BrandIcon`, `AiBriefSummary`, existing `/daily/[date]` route。
- Produces: Logo 默认彩色；每张最新日报卡片的标题、内容和外框都能进入同一个日报 URL。

- [ ] **Step 1: Write failing UI tests**

  Assert the trust-bar logo wrapper has no grayscale class and assert the daily card exposes one link covering its visible card content with the expected href.

- [ ] **Step 2: Run the focused tests and confirm RED**

  Run: `npm --workspace @nev/web test -- components/latest-briefs-grid.test.tsx app/page.test.tsx`
  Expected: the new color and whole-card assertions fail against the current classes/nested title link.

- [ ] **Step 3: Implement minimal markup changes**

  Remove the trust-bar `grayscale`/opacity treatment. Wrap the card content in a single accessible `Link` or equivalent full-card link without nested interactive elements; retain semantic `article`, date, and module labels.

- [ ] **Step 4: Run focused tests and lint**

  Run the Step 2 command and `npm --workspace @nev/web run lint`.

- [ ] **Step 5: Commit**

  ```bash
  git add packages/web/app/page.tsx packages/web/components/latest-briefs-grid.tsx packages/web/components/latest-briefs-grid.test.tsx packages/web/app/page.test.tsx
  git commit -m "fix(web): restore colorful logos and full brief card links"
  ```

### Task 3: 统一 digest 数量、排除规则、序号和 AI 工程换行

**Files:**
- Modify: `packages/ai-brief/ai_brief/config.py`
- Modify: `packages/ai-brief/ai_brief/digest/condenser.py`
- Modify: `packages/ai-brief/ai_brief/digest/generate.py`
- Modify: `packages/ai-brief/ai_brief/schema.py`（仅在数量约束需要同步时）
- Modify: `packages/ai-brief/ai_brief/templates/ai_brief.html.j2`
- Modify: `packages/ai-brief/ai_brief/templates/ai_brief.txt.j2`
- Modify: `packages/web/components/daily-brief.tsx`
- Test: `packages/ai-brief/tests/test_digest_input.py`
- Test: `packages/ai-brief/tests/test_digest_logic.py`
- Test: `packages/ai-brief/tests/test_composer.py`
- Test: `packages/web/components/daily-brief.test.tsx`

**Interfaces:**
- Consumes: `AgentTool`, `DigestStory`, `DigestSection`, `build_digest_modules`, current email templates and `DailyBrief`.
- Produces: Agent 工具 3 条且剔除指定仓库；三个模块有稳定 1-based 序号；AI 工程字段值换行显示；网站与邮件视觉语义一致。

- [ ] **Step 1: Add failing parser/generator tests**

  Add real-input tests with the three excluded repository URL/name variants mixed into valid tools; expect exactly three remaining stories and no excluded slug. Add render tests expecting `1.` prefixes and `问题：`/`方法：`/`启示：` labels followed by a line break.

- [ ] **Step 2: Run focused Python and Web tests to verify RED**

  Run: `uv run pytest -c pyproject.toml packages/ai-brief/tests/test_digest_input.py packages/ai-brief/tests/test_digest_logic.py packages/ai-brief/tests/test_composer.py -q`
  Run: `npm --workspace @nev/web test -- components/daily-brief.test.tsx`
  Expected: new count/filter/format assertions fail before implementation.

- [ ] **Step 3: Implement filtering and count changes**

  Set `AGENT_TOOLS_PICK = 3`. Add one small case-insensitive repository matcher that rejects owner/repo forms for `openai/codex`, `anthropic/claude`, and `google/gemini` before model selection. Pass only the filtered list to the selector and make the prompt request three picks. Keep the quality gate aligned with three required Agent stories.

- [ ] **Step 4: Implement shared display formatting**

  Render `loop.index` in the HTML and text digest-section macros and in `DailyBrief`. For AI 工程, render each story as a numbered field label followed by `<br>`/newline and the summary body; preserve ordinary headline/summary rendering for the other modules.

- [ ] **Step 5: Run focused tests and static checks**

  Re-run the commands from Step 2, then `ruff check packages/ai-brief/ai_brief packages/ai-brief/tests` and `npm --workspace @nev/web run typecheck`.

- [ ] **Step 6: Commit**

  ```bash
  git add packages/ai-brief/ai_brief/config.py packages/ai-brief/ai_brief/digest/condenser.py packages/ai-brief/ai_brief/digest/generate.py packages/ai-brief/ai_brief/schema.py packages/ai-brief/ai_brief/templates/ai_brief.html.j2 packages/ai-brief/ai_brief/templates/ai_brief.txt.j2 packages/web/components/daily-brief.tsx packages/ai-brief/tests packages/web/components/daily-brief.test.tsx
  git commit -m "feat(digest): expand and format agent tools"
  ```

### Task 4: 让 launchd 在质量通过时自动审批、发布和发送

**Files:**
- Modify: `ops/launchd/run-ai-generate.sh`
- Modify: `ops/launchd/run-ai-release.sh`
- Modify: `ops/launchd/install-ai-daily.sh`（仅在安装/旧任务清理需要同步时）
- Modify: `ops/launchd/README.md`
- Test: `ops/launchd/test-schedules.sh` 或新增同目录 shell 测试

**Interfaces:**
- Consumes: `ai_brief generate`, `ai_brief approve`, `ai_brief release`, project `.env`, `AI_EMAIL_SEND_ENABLED=true`。
- Produces: generate 成功且 exit 0 后自动执行同日期 approve；release 使用同日期并保留现有幂等投递；失败会写日志并以非零退出，不会发送 blocked/failed 内容。

- [ ] **Step 1: Write failing schedule tests**

  Add a shell-level test using a temporary fake `uv` executable that records arguments and returns controlled generate results. Assert a successful generate invokes `approve --date <same date>` and a nonzero generate does not invoke approve.

- [ ] **Step 2: Run the schedule test and confirm RED**

  Run: `bash ops/launchd/test-schedules.sh`
  Expected: the success-path assertion fails because the current generate runner only invokes `generate`.

- [ ] **Step 3: Implement the minimal automatic approval sequence**

  In `run-ai-generate.sh`, load the project environment through the existing Python settings path, run explicit-date generate, and only when its exit code is zero invoke `approve --date` with `AIVIZENS_OPERATOR_ID` set by the launchd environment. Leave release at 08:00 and ensure its environment reads `AI_EMAIL_SEND_ENABLED=true` from `.env`; do not add a second delivery mechanism.

- [ ] **Step 4: Run schedule tests and shell validation**

  Run `bash ops/launchd/test-schedules.sh`, `bash -n ops/launchd/run-ai-generate.sh ops/launchd/run-ai-release.sh ops/launchd/install-ai-daily.sh`, and `plutil -lint ops/launchd/com.aivizens.ai-generate.plist ops/launchd/com.aivizens.ai-release.plist`.

- [ ] **Step 5: Install and inspect the Mac mini jobs**

  Run `PROJECT_ROOT=/Users/jack/nev-brief bash ops/launchd/install-ai-daily.sh`, then inspect `launchctl print gui/$(id -u)/com.aivizens.ai-generate` and `launchctl print gui/$(id -u)/com.aivizens.ai-release`. Do not kickstart production generation until the 8/27 backfill is complete and verified.

- [ ] **Step 6: Commit**

  ```bash
  git add ops/launchd
  git commit -m "ops: auto approve passing AI briefs"
  ```

### Task 5: 读取 8 月 27 日邮件、生成并发布日报

**Files:**
- No tracked source changes expected; use the production CLI and record evidence in the ignored task report.
- Evidence: `.superpowers/sdd/2026-08-27-aivizens-site-daily-automation-fixes/task-5-report.md`

**Interfaces:**
- Consumes: Peter Gmail IMAP digest emails for 2026-08-27 and production Supabase/Resend credentials from `/Users/jack/nev-brief/.env`.
- Produces: one quality-passing `published` brief at `/daily/2026-08-27` and one sent delivery per active subscriber.

- [ ] **Step 1: Search and parse the five 8/27 digest emails without sending**

  Use the project Gmail adapter/CLI with `AI_EMAIL_SEND_ENABLED=false`; verify all five required digest kinds are dated 2026-08-27 and that parser counts are nonzero.

- [ ] **Step 2: Generate the candidate**

  Run `AIVIZENS_OPERATOR_ID=production-backfill AI_EMAIL_SEND_ENABLED=false uv run python -m ai_brief generate --date 2026-08-27` and record only run ID, status, module counts, blocker count, warning codes, and digest counts.

- [ ] **Step 3: Inspect quality and approve**

  Proceed only for `awaiting_approval` with zero blockers; run `AIVIZENS_OPERATOR_ID=jack uv run python -m ai_brief approve --date 2026-08-27`.

- [ ] **Step 4: Release and create deliveries**

  Run `AI_EMAIL_SEND_ENABLED=false uv run python -m ai_brief release --date 2026-08-27`; verify the brief is `published` and deliveries are pending before enabling actual send.

- [ ] **Step 5: Send and verify**

  Run `AI_EMAIL_SEND_ENABLED=true uv run python -m ai_brief deliver --date 2026-08-27`; verify Resend success, `sent_count`, `pending_count=0`, and no failed delivery rows. Do not resend if an existing row is already `sent`.

- [ ] **Step 6: Verify the public page**

  Request `https://aivizens.com/daily/2026-08-27` with a no-proxy HTTP client and assert HTTP 200 plus the generated subject/date in the body.

### Task 6: Full verification, GitHub sync, deployment and tomorrow’s runbook

**Files:**
- Modify: `ops/launchd/README.md` if the installed command or automatic-approval behavior differs from the documented runbook.
- Evidence: `.superpowers/sdd/2026-08-27-aivizens-site-daily-automation-fixes/task-6-report.md`

**Interfaces:**
- Consumes: all prior task outputs and production evidence.
- Produces: clean tracked worktree, remote `main` containing the changes, successful Vercel deployment, and a tested 06:45/08:00 runbook.

- [ ] **Step 1: Run the full verification gate**

  Run `make verify`, the full AI-brief pytest suite, the full Web Vitest suite, and the relevant Playwright subscription/archive suites. Record exact pass/fail counts and any pre-existing warnings.

- [ ] **Step 2: Push and merge**

  Confirm `git status -sb` is clean, push `codex/aivizens-production-launch`, open/refresh the PR, and merge to `main` only after the intended checks are reviewed. Confirm `git ls-remote origin refs/heads/main` equals the merge commit.

- [ ] **Step 3: Verify Vercel production**

  Poll `https://aivizens.com/`, `/daily/2026-08-26`, and `/daily/2026-08-27`; assert homepage subscription UI, colorful logo assets, whole-card links, and HTTP 200 for both published articles.

- [ ] **Step 4: Verify the next scheduled date**

  Confirm the Mac mini has the two exact labels and times: `com.aivizens.ai-generate` at 06:45 and `com.aivizens.ai-release` at 08:00 Asia/Shanghai. Confirm `.env` has `AI_EMAIL_SEND_ENABLED=true` and the release runner does not use the retired `daily` command.

- [ ] **Step 5: Commit documentation and hand off**

  ```bash
  git add ops/launchd/README.md
  git commit -m "docs(ops): document automatic AI brief release"
  git push
  ```
