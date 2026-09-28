# AIVIZENS OPC Double-Case V4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate every new AIVIZENS daily brief with two structured OPC cases, render both consistently on the website and in email, and preserve all historical V1/V2/V3 briefs.

**Architecture:** Add a V4 frozen-content contract with `opc_cases` containing exactly two structured cases while retaining the V3 `opc_case` contract. Parse the two labeled Hermes cases without ranking them, normalize each revenue, bind each case to its matching attachment, then enforce fail-closed quality rules before shared website and email renderers consume the frozen V4 content.

**Tech Stack:** Python 3.12+/Pydantic/selectolax/Pillow/Jinja2/pytest, TypeScript/Next.js 15/Zod/React/Vitest, Supabase JSONB.

**Spec:** `docs/superpowers/specs/2026-09-27-opc-double-case-v4-design.md`

## Global Constraints

- New generated briefs use `version: 4`; historical V1/V2/V3 JSON remains valid and is never rewritten.
- V4 requires exactly two OPC cases in source order and never ranks, sorts, or removes them by revenue.
- Each V4 case requires `background` at 1–100 Unicode code points, `solution` at 1–120, and `insight` at 1–80.
- Case 1 binds only to attachment 1 and case 2 only to attachment 2; never substitute one case's image for the other.
- Revenue remains positive USD monthly revenue; ARR divides by 12 and non-USD values use the existing ECB conversion.
- Website, HTML email, and text email consume the same frozen V4 fields in the same order.
- V4 overview remains exactly five bullets: combined OPC titles, Today AI 1/2/4, AI Masters 1.
- V4 editorial ends with `今日给大家分享两个 OPC 案例，详情见下方。` and remains at most 220 code points.
- Any missing/invalid case field, image, revenue, or trusted URL blocks release and delivery with an indexed quality path.
- No historical backfill, subscriber broadcast, schedule change, or unrelated refactor belongs in this plan.

## Review Focus

- Hermes may wrap labels in `<strong>`, nested `<div>`, or extra whitespace; Task 2 pins label extraction to normalized visible text rather than one exact tag shape.
- Supplementary Unicode characters can differ between Python length and JavaScript UTF-16 length; Task 1 pins shared 100/120/80 code-point boundaries in both runtimes.
- Attachment filenames may contain duplicate or conflicting case markers; Task 3 proves ambiguity blocks that case instead of cross-binding an image.
- One revenue may normalize while the other fails; Task 3 proves the whole V4 OPC result fails closed with no partial list.
- Homepage queries return mixed V1–V4 rows; Task 5 proves V3 single-case and V4 double-case summaries coexist and invalid rows are skipped without hiding valid ones.

---

### Task 1: Add the Cross-Language V4 Frozen Contract

**Files:**
- Modify: `packages/ai-brief/ai_brief/schema.py`
- Modify: `packages/ai-brief/tests/test_schema.py`
- Modify: `packages/web/lib/ai-briefs.ts`
- Modify: `packages/web/lib/ai-briefs.test.ts`
- Modify: `tests/fixtures/opc-unicode-contract.json`
- Modify: `packages/web/test/fixtures/published-brief.ts`
- Modify: `packages/web/test/fixtures/published-brief.test.ts`

**Interfaces:**
- Consumes: existing `OpcCase`, `AiBriefContent`, `AiBriefContentSchema`, and the shared Unicode boundary fixture.
- Produces: Python `OpcCaseV4`; TypeScript `OpcCaseV4Schema`; `AiBriefContent.version: 1 | 2 | 3 | 4`; `opc_cases: list[OpcCaseV4]`/array; `build_v4_intro_bullets(opc_cases, today_ai, ai_masters) -> list[str]`.

- [ ] **Step 1: Write Python contract RED tests**

Add `test_v4_requires_exactly_two_structured_opc_cases`, `test_v4_rejects_legacy_single_case`, and parametrized 100/120/80 Unicode boundary tests. Assert V3 still requires one `opc_case` and accepts no `opc_cases`.

- [ ] **Step 2: Run the Python contract tests and observe RED**

Run: `UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_schema.py -q`

Expected: FAIL because version 4, `OpcCaseV4`, `opc_cases`, and V4 overview construction do not exist.

- [ ] **Step 3: Implement the minimal Python V4 schema**

Define `OpcCaseV4` with the exact fields and bounds from the spec. Extend `AiBriefContent` to version 4 with `opc_cases: list[OpcCaseV4] = Field(default_factory=list, max_length=2)`. Enforce: V3 has one `opc_case` and empty `opc_cases`; V4 has `opc_case is None` and exactly two `opc_cases`; V1/V2 keep both OPC fields empty. Extend the frozen-content cleanup rule to V4.

Define:

```python
def build_v4_intro_bullets(
    opc_cases: list[OpcCaseV4],
    today_ai: DigestSection | None,
    ai_masters: DigestSection | None,
) -> list[str]: ...
```

The first bullet is exactly `💡 OPC案例：{case1.headline}；{case2.headline}`.

- [ ] **Step 4: Write TypeScript contract RED tests**

Add tests for a valid V4 fixture, missing/one/three cases, nonempty `opc_case`, the shared supplementary-Unicode boundaries, and continued V3 parsing.

- [ ] **Step 5: Run the TypeScript contract tests and observe RED**

Run: `npm --workspace @nev/web test -- lib/ai-briefs.test.ts test/fixtures/published-brief.test.ts`

Expected: FAIL because the Zod contract only accepts versions 1–3 and has no `opc_cases`.

- [ ] **Step 6: Implement the minimal TypeScript V4 schema and fixture**

Add the strict `OpcCaseV4Schema`, version 4, `opc_cases`, and V4 `superRefine` rules matching Pydantic. Extend the shared fixture with a frozen V4 brief containing two distinct cases while preserving the V3 fixture.

- [ ] **Step 7: Run both contract suites GREEN**

Run:

```bash
UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_schema.py -q
npm --workspace @nev/web test -- lib/ai-briefs.test.ts test/fixtures/published-brief.test.ts
```

Expected: all selected tests PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add packages/ai-brief/ai_brief/schema.py packages/ai-brief/tests/test_schema.py packages/web/lib/ai-briefs.ts packages/web/lib/ai-briefs.test.ts packages/web/test/fixtures/published-brief.ts packages/web/test/fixtures/published-brief.test.ts tests/fixtures/opc-unicode-contract.json
git commit -m "feat(content): add V4 OPC double-case contract"
```

### Task 2: Parse Two Structured Hermes Cases

**Files:**
- Modify: `packages/ai-brief/ai_brief/digest/models.py`
- Modify: `packages/ai-brief/ai_brief/digest/opc_parser.py`
- Create: `packages/ai-brief/tests/fixtures/opc_sharing_v4.html`
- Preserve: `packages/ai-brief/tests/fixtures/opc_sharing_2026-09-14.html`
- Modify: `packages/ai-brief/tests/test_opc_parser.py`

**Interfaces:**
- Consumes: the existing `Revenue` parser and exact case header convention.
- Produces: `OpcCaseCandidate(index, sharer, headline, background, solution, insight, revenue, url)` and `parse_opc_digest(html: str) -> list[OpcCaseCandidate]` in source index order.

- [ ] **Step 1: Add a sanitized V4 fixture with the new labeled format**

Give both cases unique background, solution, insight, revenue, and HTTPS source values. Include nested `<strong>` labels and harmless whitespace so the fixture represents Hermes HTML rather than a plain-string-only happy path. Keep the historical V3 fixture unchanged for backward-compatibility tests.

- [ ] **Step 2: Write parser RED tests**

Assert both cases expose all three structured fields. Add parametrized tests for each missing/empty/duplicate label, duplicate case headers, HTTP URLs, unknown revenue periods, and labels wrapped in `<strong>` or nested `<div>`. Add a source-order assertion independent of revenue.

- [ ] **Step 3: Run parser tests and observe RED**

Run: `UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_opc_parser.py -q`

Expected: FAIL because candidates only expose `body` and the parser only captures the first unlabeled paragraph.

- [ ] **Step 4: Implement strict label parsing**

Replace `body` with `background`, `solution`, and `insight`. Normalize visible whitespace with `_clean`, identify field labels by normalized text rather than tag name, require each label exactly once, preserve the text after the first label separator, and keep the existing duplicate-header exclusion. Do not enforce display truncation or silently shorten source text.

- [ ] **Step 5: Run parser tests GREEN**

Run: `UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_opc_parser.py -q`

Expected: all parser and revenue tests PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add packages/ai-brief/ai_brief/digest/models.py packages/ai-brief/ai_brief/digest/opc_parser.py packages/ai-brief/tests/fixtures/opc_sharing_v4.html packages/ai-brief/tests/test_opc_parser.py
git commit -m "feat(opc): parse two structured cases"
```

### Task 3: Build, Normalize, and Image-Bind Both Cases

**Files:**
- Modify: `packages/ai-brief/ai_brief/digest/exchange_rates.py`
- Modify: `packages/ai-brief/ai_brief/digest/generate.py`
- Modify: `packages/ai-brief/tests/test_exchange_rates.py`
- Modify: `packages/ai-brief/tests/test_workflow.py`

**Interfaces:**
- Consumes: Task 1 `OpcCaseV4`; Task 2 `OpcCaseCandidate`; existing `monthly_revenue_usd`, `format_monthly_usd`, attachment validation, hero-band crop, and uploader.
- Produces: `NormalizedOpcCase`; `normalize_case_revenue(candidate, rates) -> NormalizedOpcCase`; `build_opc_cases(brief_date, digest, rates_loader=fetch_ecb_rates) -> tuple[list[OpcCaseV4], int]`; `build_v4_editorial(editorial: str) -> str`; `DigestBundle.opc_cases`.

- [ ] **Step 1: Write revenue normalization RED tests**

Assert independent normalization for USD MRR, USD ARR, and CNY MRR without comparison or sorting. Assert missing/zero/nonfinite rates raise `RevenueConversionError` for the whole operation. Keep legacy `select_highest_case` tests passing for historical compatibility.

- [ ] **Step 2: Run revenue tests and observe RED**

Run: `UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_exchange_rates.py -q`

Expected: FAIL because `NormalizedOpcCase` and `normalize_case_revenue` do not exist.

- [ ] **Step 3: Implement per-case revenue normalization**

Add the new interface using existing conversion and formatting functions. `converted` is true when currency is not USD or period is not MRR. Do not remove `select_highest_case` in this task.

- [ ] **Step 4: Write double-case construction RED tests**

Cover: two cases returned in indices 1/2 even when case 1 earns less; one rates-loader call; two distinct upload paths; indexed and ordered-fallback attachment binding; duplicate/conflicting filename markers; unusable second image; second revenue failure after first succeeds; upload failure; and no partial case list after a structural or revenue failure. For an image problem, preserve both indexed cases with an empty image only on the affected case so Task 4 can report the precise blocker. Assert Qwen is never called.

Add exact overview and editorial assertions:

```python
assert build_v4_intro_bullets(cases, today_ai, ai_masters)[0] == (
    "💡 OPC案例：First title；Second title"
)
assert build_v4_editorial("核心判断。与此同时，旧内容") == (
    "核心判断。今日给大家分享两个 OPC 案例，详情见下方。"
)
```

- [ ] **Step 5: Run workflow tests and observe RED**

Run: `UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_workflow.py -q`

Expected: FAIL because generation still selects one highest-revenue case.

- [ ] **Step 6: Implement deterministic double-case construction**

Replace the new-generation path with `build_opc_cases`. Load rates once only when needed, normalize both before uploading either result, resolve both attachments without cross-substitution, and upload to separate `opc-case-1`/`opc-case-2` paths. Return `([], parsed_count)` on structural or conversion failure. For a missing, unusable, duplicate, or ambiguous image mapping, keep the affected case with `header_image=""` via `model_construct` so the indexed quality gate blocks it without losing source evidence. Construct bounded narrative candidates the same way so over-limit text reaches the schema quality boundary with its exact field path. Let upload/network exceptions reach the existing durable failure boundary.

Update `DigestBundle` and `build_digest_modules` to carry `opc_cases` and the unchanged candidate count. Add `build_v4_editorial`, preserving sentence-boundary clipping and the 220-character limit.

- [ ] **Step 7: Run Task 3 suites GREEN**

Run:

```bash
UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_exchange_rates.py packages/ai-brief/tests/test_workflow.py -q
```

Expected: all selected tests PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add packages/ai-brief/ai_brief/digest/exchange_rates.py packages/ai-brief/ai_brief/digest/generate.py packages/ai-brief/tests/test_exchange_rates.py packages/ai-brief/tests/test_workflow.py
git commit -m "feat(opc): build both structured cases"
```

### Task 4: Assemble V4 and Enforce Fail-Closed Quality

**Files:**
- Modify: `packages/ai-brief/ai_brief/runner.py`
- Modify: `packages/ai-brief/ai_brief/quality.py`
- Modify: `packages/ai-brief/ai_brief/schema.py`
- Modify: `packages/ai-brief/ai_brief/storage.py`
- Modify: `packages/ai-brief/tests/test_quality.py`
- Modify: `packages/ai-brief/tests/test_workflow.py`
- Modify: `packages/ai-brief/tests/test_storage.py`
- Modify: `packages/ai-brief/tests/test_digest_run_storage.py`

**Interfaces:**
- Consumes: Task 1 V4 schema/overview builder and Task 3 `DigestBundle.opc_cases`/editorial builder.
- Produces: `_build_brief_without_lookup(...) -> AiBriefContent` with version 4; indexed OPC quality paths; `opc_case_count=2`; `opc_monthly_revenue_usd_total`.

- [ ] **Step 1: Write V4 assembly RED tests**

Assert generated payloads use version 4, set `opc_case=None`, persist two `opc_cases` in source order, construct exactly five overview bullets, and use the fixed double-case editorial sentence. Assert V3 stored content remains readable and storage normalization does not rewrite it.

- [ ] **Step 2: Write quality RED tests**

Mutate each case independently: missing case, overlong background/solution/insight, empty image, HTTP image, source URL absent from the OPC digest, HTTP source URL, nonpositive revenue, and swapped order. Assert release is blocked and paths identify `opc_cases[0]` or `opc_cases[1]` plus the field.

Assert metrics equal:

```python
assert metrics["opc_candidate_count"] == 2
assert metrics["opc_case_count"] == 2
assert metrics["opc_monthly_revenue_usd_total"] == case1_usd + case2_usd
```

- [ ] **Step 3: Run quality/workflow/storage tests and observe RED**

Run:

```bash
UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_quality.py packages/ai-brief/tests/test_workflow.py packages/ai-brief/tests/test_storage.py packages/ai-brief/tests/test_digest_run_storage.py -q
```

Expected: FAIL because the runner still assembles V3 and quality/storage only know one case.

- [ ] **Step 4: Assemble V4 in the runner**

Use `build_v4_intro_bullets` and `build_v4_editorial`, set version 4, persist `opc_cases`, and leave `opc_case` empty. Preserve `model_construct` fallback so invalid candidates reach the quality boundary rather than becoming opaque generation failures.

- [ ] **Step 5: Extend quality paths, codes, and metrics**

Allow indexed `opc_cases[N].field` paths only for indices 0 and 1 and the approved V4 fields. Reuse `schema_invalid` for bounded-string/structure failures and existing image/URL issue codes for those fields. Validate both URLs against the trusted digest. Add `opc_monthly_revenue_usd_total` to the safe metric catalog and numeric persistence allowlist.

- [ ] **Step 6: Keep storage and run metadata backward compatible**

Normalize V4 without touching V3, persist only the numeric count/total and existing safe digest attachment metadata, and never persist email HTML or the three narrative fields in run metadata outside the frozen brief content.

- [ ] **Step 7: Run Task 4 suites GREEN**

Run the Step 3 command again.

Expected: all selected tests PASS with indexed blocker paths and safe metrics.

- [ ] **Step 8: Commit Task 4**

```bash
git add packages/ai-brief/ai_brief/runner.py packages/ai-brief/ai_brief/quality.py packages/ai-brief/ai_brief/schema.py packages/ai-brief/ai_brief/storage.py packages/ai-brief/tests/test_quality.py packages/ai-brief/tests/test_workflow.py packages/ai-brief/tests/test_storage.py packages/ai-brief/tests/test_digest_run_storage.py
git commit -m "feat(workflow): enforce V4 OPC quality"
```

### Task 5: Render Both Cases on Website and Email

**Files:**
- Modify: `packages/ai-brief/ai_brief/templates/ai_brief.html.j2`
- Modify: `packages/ai-brief/ai_brief/templates/ai_brief.txt.j2`
- Modify: `packages/ai-brief/tests/test_composer.py`
- Modify: `packages/web/components/daily-brief.tsx`
- Modify: `packages/web/components/daily-brief.test.tsx`
- Modify: `packages/web/lib/ai-briefs.ts`
- Modify: `packages/web/lib/ai-briefs.test.ts`
- Modify: `packages/web/test/fixtures/published-brief.ts`

**Interfaces:**
- Consumes: Task 1 `opc_cases` V4 contract and preserved V3 `opc_case`.
- Produces: one numbered V4 OPC module containing two ordered case blocks; V4-compatible homepage summary projection; unchanged V3 single-case rendering.

- [ ] **Step 1: Write email renderer RED tests**

Assert HTML and text output each contain one `OPC分享` heading, one `一、OPC案例` module label, case 1 before case 2, six narrative labels, two distinct image URLs, two revenue displays, and two source links. Assert V3 still renders the existing single-case layout.

- [ ] **Step 2: Run composer tests and observe RED**

Run: `UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_composer.py -q`

Expected: FAIL because templates only call `opc_section(brief.opc_case)` for V3.

- [ ] **Step 3: Implement backward-compatible email templates**

Keep the V3 macro path unchanged. Add a V4 table-based module with one black outer border and two internal case sections separated by a border. Render labels and values as separate blocks in the exact spec order. Update plain text with the same two-case order.

- [ ] **Step 4: Write website component RED tests**

Assert one region named `一、OPC案例`, child headings `案例 1` and `案例 2`, source order, both full-width auto-height images, all six labeled paragraphs, revenues, and links. Assert V3 keeps its single-case region and V1/V2 show no OPC module.

- [ ] **Step 5: Write mixed-version homepage RED tests**

Return mixed V1/V2/V3/V4 summary rows from the Supabase mock. Add an `opc_cases` JSON projection for V4, require exactly two cases for V4 summaries, label both V3 and V4 cards `OPC案例`, and prove one malformed row is skipped without removing valid neighbors.

- [ ] **Step 6: Run web tests and observe RED**

Run:

```bash
npm --workspace @nev/web test -- components/daily-brief.test.tsx lib/ai-briefs.test.ts
```

Expected: FAIL because the component and summary schema only understand V3 `opc_case`.

- [ ] **Step 7: Implement website and homepage compatibility**

Keep `OpcBlock` for V3. Add a V4 block consuming the two-item array and render one outer module. Extend summary version parsing to `"4"`, select `opc_cases:content->opc_cases`, validate exactly two V4 cases, and include the OPC module label for both V3 and V4. Do not change homepage ordering, ISR, or cache-refresh logic.

- [ ] **Step 8: Run Task 5 suites GREEN**

Run:

```bash
UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_composer.py -q
npm --workspace @nev/web test -- components/daily-brief.test.tsx lib/ai-briefs.test.ts
```

Expected: all selected tests PASS.

- [ ] **Step 9: Commit Task 5**

```bash
git add packages/ai-brief/ai_brief/templates/ai_brief.html.j2 packages/ai-brief/ai_brief/templates/ai_brief.txt.j2 packages/ai-brief/tests/test_composer.py packages/web/components/daily-brief.tsx packages/web/components/daily-brief.test.tsx packages/web/lib/ai-briefs.ts packages/web/lib/ai-briefs.test.ts packages/web/test/fixtures/published-brief.ts
git commit -m "feat(render): show both OPC cases"
```

### Task 6: End-to-End Acceptance and Release Readiness

**Files:**
- Modify if needed for coverage only: `packages/ai-brief/tests/test_cli_workflow.py`
- Modify if needed for coverage only: `docs/runbooks/production-inventory.md`
- Verify: all files changed in Tasks 1–5

**Interfaces:**
- Consumes: the completed V4 pipeline and renderers.
- Produces: a reviewed, fully verified feature branch ready for PR; no production mutation or subscriber email.

- [ ] **Step 1: Add one end-to-end frozen V4 workflow test**

Generate from a two-case digest envelope with two attachments, approve/release through mocked storage, and assert the published JSON and composed output both contain the two structured cases. Assert a missing second insight creates no published content and no delivery row.

- [ ] **Step 2: Run the end-to-end test GREEN**

Run: `UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest packages/ai-brief/tests/test_cli_workflow.py -q`

Expected: all selected tests PASS.

- [ ] **Step 3: Update operational documentation only where the V4 contract changed**

Document that new OPC input requires two complete structured cases and that the first post-deployment actual Hermes email should be inspected for label compatibility before the scheduled publish window. Do not alter schedules or secrets.

- [ ] **Step 4: Run the full repository gate**

Run:

```bash
env -u QWEN_MODEL \
  UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache \
  SUPABASE_URL=https://example.invalid \
  SUPABASE_SERVICE_ROLE_KEY=test-service-role \
  DEEPSEEK_API_KEY=test-deepseek-key \
  RESEND_API_KEY=test-resend-key \
  ALLOW_UNAVAILABLE_HOMEPAGE_BUILD=true \
  HOMEPAGE_REVALIDATE_SECRET=0123456789abcdef0123456789abcdef \
  make verify
```

Expected: Python, Web, ops contract, Ruff, mypy, ESLint, TypeScript, Next production build, brand assets, and homepage ISR all PASS; only the existing header/footer `<img>` lint warnings may remain.

- [ ] **Step 5: Run final static checks**

Run:

```bash
git diff --check origin/main...HEAD
git status --short --branch
```

Expected: no whitespace errors and no uncommitted product changes.

- [ ] **Step 6: Commit final acceptance coverage/docs if changed**

```bash
git add packages/ai-brief/tests/test_cli_workflow.py docs/runbooks/production-inventory.md
git commit -m "test(opc): cover V4 release workflow"
```

- [ ] **Step 7: Request whole-branch code review**

Review `origin/main...HEAD` against the spec, with special attention to the five Review Focus failure modes, historical V3 compatibility, fail-closed delivery behavior, and the absence of subscriber side effects.

Expected: no Critical or Important findings remain before PR creation.

## Production Handoff After Implementation

Production actions are deliberately outside implementation authorization. After the branch is green and reviewed, present the normal integration choices. A later explicit production authorization must cover:

1. Push branch and create PR.
2. Merge after GitHub/Vercel checks pass.
3. Sync `/Users/jack/nev-brief` without overwriting local executable-mode differences.
4. Deploy Vercel Production and verify V4 schema/rendering.
5. Inspect the first real new-format Hermes email and generated candidate before allowing the scheduled release to send to subscribers.
6. Send a controlled test email only if the user separately authorizes an exact recipient.
