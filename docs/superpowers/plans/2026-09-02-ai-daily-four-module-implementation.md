# AI Daily Four-Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate future AIVIZENS AI daily briefs as a v2 four-module issue, with exactly five Today AI stories (three overseas and two domestic), while rendering historical v1 issues unchanged.

**Architecture:** The generator will select and label the Today AI regional quota before any model call, then persist new issues as `version=2`. The quality gate will enforce the v2 quota and four required modules. Web and email renderers will branch only on `content.version`: v1 keeps the historical five-module presentation, while v2 shows the requested numbered four-module presentation.

**Tech Stack:** Python 3.12, Pydantic, pytest, Jinja2, Next.js/TypeScript, Zod, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-02-ai-daily-four-module-design.md`

## Global Constraints

- New briefs use content version `2`; historical version `1` JSON remains valid and unchanged.
- Today AI v2 contains exactly five stories: three `海外新闻` and two `国内新闻`.
- A shortage in either regional quota blocks generation before approval, release, and delivery.
- New briefs do not generate or require AI工程; historical v1 pages and emails retain it.
- The four v2 headings are exactly `一、今日AI`, `二、AI大神`, `三、AI研究`, and `四、Agent工具`.
- Do not modify historical rows, subscription data, Resend configuration, or launchd schedules.
- Preserve the existing uncommitted executable-bit changes in `ops/launchd/`.

---

## File Structure

- Modify `packages/ai-brief/ai_brief/config.py`: define Today AI total and regional quota constants.
- Modify `packages/ai-brief/ai_brief/digest/generate.py`: select and normalize five regional event stories; stop building AI工程 for new bundles.
- Modify `packages/ai-brief/ai_brief/digest/condenser.py`: make the Today AI prompt describe five supplied stories.
- Modify `packages/ai-brief/ai_brief/schema.py`: accept v1 and v2 content and allow the v2 quota quality issue.
- Modify `packages/ai-brief/ai_brief/runner.py`: persist generated briefs as v2 while retaining legacy fields for read compatibility.
- Modify `packages/ai-brief/ai_brief/quality.py`: enforce v2 module and Today AI regional constraints, but retain v1 validation behavior.
- Modify `packages/web/lib/ai-briefs.ts`: parse both versions and derive module labels from each version's visible modules.
- Modify `packages/web/components/daily-brief.tsx`: render v1's legacy blocks or v2's four numbered blocks.
- Modify `packages/ai-brief/ai_brief/templates/ai_brief.html.j2` and `packages/ai-brief/ai_brief/templates/ai_brief.txt.j2`: render version-specific digest section titles and omit engineering from v2.
- Modify focused Python and TypeScript tests under `packages/ai-brief/tests/` and `packages/web/`.

## Task 1: Deterministic v2 Today AI selection

**Files:**
- Modify: `packages/ai-brief/ai_brief/config.py:114-119`
- Modify: `packages/ai-brief/ai_brief/digest/generate.py:250-279,438-472`
- Modify: `packages/ai-brief/ai_brief/digest/condenser.py:43-117`
- Test: `packages/ai-brief/tests/test_digest_logic.py`
- Test: `packages/ai-brief/tests/test_digest_input.py`

**Interfaces:**
- Consumes: `list[EventItem]`, where `EventItem.category` begins with `国内` for domestic source cards.
- Produces: `_select_today_ai_items(items: list[EventItem]) -> list[EventItem]`, returning either exactly five normalized stories or an empty list.
- Produces: `DigestBundle.today_ai` containing five `DigestStory` entries, or `None` when a regional quota cannot be met.

- [ ] **Step 1: Write failing quota tests**

Add an event fixture with source-order candidates: four overseas and three domestic. Assert the helper returns the first three overseas followed by the first two domestic, with labels exactly `海外新闻`, `海外新闻`, `海外新闻`, `国内新闻`, `国内新闻`. Add a second fixture with only one domestic event and assert the helper returns an empty list.

```python
def test_select_today_ai_items_keeps_three_overseas_then_two_domestic() -> None:
    selected = _select_today_ai_items([
        _event(1, category="海外大模型公司"),
        _event(2, category="国内大模型公司"),
        _event(3, category="海外"),
        _event(4, category="国内"),
        _event(5, category="海外"),
    ])

    assert [item.index for item in selected] == [1, 3, 5, 2, 4]
    assert [item.label for item in selected] == ["海外新闻"] * 3 + ["国内新闻"] * 2


def test_select_today_ai_items_rejects_missing_domestic_quota() -> None:
    assert _select_today_ai_items([_event(1, category="国内"), _event(2, category="海外")]) == []
```

- [ ] **Step 2: Run the focused quota tests to verify they fail**

Run: `uv run pytest packages/ai-brief/tests/test_digest_logic.py -q -p no:cacheprovider`  
Expected: FAIL because `_select_today_ai_items` and the v2 quota behavior do not exist.

- [ ] **Step 3: Implement minimal deterministic selection**

In `config.py`, replace the old top-three meaning with explicit constants:

```python
TODAY_AI_OVERSEAS_COUNT = 3
TODAY_AI_DOMESTIC_COUNT = 2
TODAY_AI_TOP_N = TODAY_AI_OVERSEAS_COUNT + TODAY_AI_DOMESTIC_COUNT
```

In `generate.py`, use `dataclasses.replace` so source parser objects are never mutated:

```python
def _select_today_ai_items(items: list[EventItem]) -> list[EventItem]:
    overseas = [item for item in items if not item.category.startswith("国内")]
    domestic = [item for item in items if item.category.startswith("国内")]
    if len(overseas) < config.TODAY_AI_OVERSEAS_COUNT or len(domestic) < config.TODAY_AI_DOMESTIC_COUNT:
        return []
    return [
        *(replace(item, label="海外新闻") for item in overseas[:config.TODAY_AI_OVERSEAS_COUNT]),
        *(replace(item, label="国内新闻") for item in domestic[:config.TODAY_AI_DOMESTIC_COUNT]),
    ]
```

Call the helper in `_build_today_ai` instead of slicing the first `TODAY_AI_TOP_N` parsed events. If it returns empty, log the quota failure and return `today_ai=None` without invoking DeepSeek or Qwen. Remove the `_build_engineering` invocation from `build_digest_modules` and return `ai_engineering=None`; leave the dataclass field in place for legacy read compatibility.

Update the Today AI prompt text from three supplied stories to five supplied stories. Keep the current subject, preheader, editorial, and intro-bullet output schema unchanged; only summaries must cover all supplied story indexes.

- [ ] **Step 4: Run focused generator tests**

Run: `uv run pytest packages/ai-brief/tests/test_digest_logic.py packages/ai-brief/tests/test_digest_input.py -q -p no:cacheprovider`  
Expected: PASS, including quota ordering, label normalization, and no engineering section in a newly built bundle.

- [ ] **Step 5: Commit the generator change**

```bash
git add packages/ai-brief/ai_brief/config.py \
  packages/ai-brief/ai_brief/digest/generate.py \
  packages/ai-brief/ai_brief/digest/condenser.py \
  packages/ai-brief/tests/test_digest_logic.py \
  packages/ai-brief/tests/test_digest_input.py
git commit -m "feat(ai-brief): balance today AI regions"
```

## Task 2: Versioned content contract and v2 quality gate

**Files:**
- Modify: `packages/ai-brief/ai_brief/schema.py:20-100,200-223`
- Modify: `packages/ai-brief/ai_brief/runner.py:90-121,330-354`
- Modify: `packages/ai-brief/ai_brief/quality.py:20-57,438-570`
- Test: `packages/ai-brief/tests/test_quality.py`
- Test: `packages/ai-brief/tests/test_workflow.py`

**Interfaces:**
- Consumes: `AiBriefContent.version` and `DigestSection.stories` labels.
- Produces: v2 briefs with `version=2`, `ai_engineering=None`, and a quality report that rejects a wrong Today AI count or regional label count.
- Preserves: v1 quality behavior and existing AI工程 data for historical reads.

- [ ] **Step 1: Write failing v2 quality tests**

Create a valid v2 brief with five Today AI stories and the required AI大神, AI研究, and Agent工具 sections. Add parameterized invalid cases for four Today AI stories, four overseas plus one domestic, and missing Agent工具. Confirm a v1 fixture with three Today AI stories and AI工程 still passes its legacy rule set.

```python
def test_v2_requires_three_overseas_and_two_domestic_today_ai() -> None:
    report = validate_brief(_v2_brief(labels=["海外新闻"] * 4 + ["国内新闻"]), _fresh_digests(), ...)

    assert not report.passed
    assert any(issue.code == "today_ai_region_quota_invalid" for issue in report.blockers)


def test_v1_keeps_legacy_today_ai_and_engineering_compatibility() -> None:
    assert validate_brief(_v1_brief(), _fresh_digests(), ...).passed
```

- [ ] **Step 2: Run focused quality tests to verify they fail**

Run: `uv run pytest packages/ai-brief/tests/test_quality.py packages/ai-brief/tests/test_workflow.py -q -p no:cacheprovider`  
Expected: FAIL because the schema accepts only v1 and the quality gate has no v2 quota rule.

- [ ] **Step 3: Implement version-aware validation**

Change the Python schema version field from a v1-only literal to `Literal[1, 2] = 1`. Add `today_ai_region_quota_invalid` to the allowlisted quality issue codes and allowed paths.

In `runner._build_brief_without_lookup`, set only newly generated content to `version=2` and set `ai_engineering=None`. Do not alter the storage schema or existing rows.

In `validate_brief`, branch on `brief.version`:

```python
if brief.version == 2:
    labels = [story.label for story in _section(brief, "today_ai").stories] if _section(brief, "today_ai") else []
    if len(labels) != 5 or labels.count("海外新闻") != 3 or labels.count("国内新闻") != 2:
        blockers.append(_issue("today_ai_region_quota_invalid", "Today AI requires three overseas and two domestic stories.", "today_ai"))
    required_tool_sections = ("ai_research", "agent_tools")
else:
    required_tool_sections = _TOOL_SECTIONS
```

For v2, require AI大神, AI研究, and Agent工具, and do not make the engineering digest stale or missing status a blocker. Retain all current v1 freshness, count, and AI工程 behavior unchanged.

- [ ] **Step 4: Run focused quality and workflow tests**

Run: `uv run pytest packages/ai-brief/tests/test_quality.py packages/ai-brief/tests/test_workflow.py -q -p no:cacheprovider`  
Expected: PASS, proving v2 blocks invalid ratios before release and v1 remains valid.

- [ ] **Step 5: Commit the v2 contract and gate**

```bash
git add packages/ai-brief/ai_brief/schema.py \
  packages/ai-brief/ai_brief/runner.py \
  packages/ai-brief/ai_brief/quality.py \
  packages/ai-brief/tests/test_quality.py \
  packages/ai-brief/tests/test_workflow.py
git commit -m "feat(ai-brief): enforce four-module v2 briefs"
```

## Task 3: Version-aware website and email rendering

**Files:**
- Modify: `packages/web/lib/ai-briefs.ts:55-130`
- Modify: `packages/web/components/daily-brief.tsx:20-28,150-170`
- Modify: `packages/ai-brief/ai_brief/templates/ai_brief.html.j2:18-65,95-138`
- Modify: `packages/ai-brief/ai_brief/templates/ai_brief.txt.j2:19-59`
- Test: `packages/web/components/daily-brief.test.tsx`
- Test: `packages/web/lib/ai-briefs.test.ts`
- Test: `packages/ai-brief/tests/test_composer.py`

**Interfaces:**
- Consumes: persisted `version: 1 | 2` content.
- Produces: v1's legacy labels and AI工程 display; v2's four numbered labels with no engineering block in web, HTML email, or plain-text email.

- [ ] **Step 1: Write failing renderer tests**

Add a v2 fixture with four sections and five Today AI stories. Assert the web component contains all four exact numbered headings, contains no `AI工程`, and shows all five Today AI headlines. Keep the existing v1 fixture assertions for `AI工程` and unnumbered labels.

Add Zod parsing tests that accept both `version: 1` historical JSON and `version: 2` JSON. Add composer template tests that render `一、今日AI` and never render `AI工程` for v2, while preserving v1's existing `AI工程` output.

```tsx
expect(screen.getByRole("heading", { name: "一、今日AI" })).toBeInTheDocument();
expect(screen.getByRole("heading", { name: "四、Agent工具" })).toBeInTheDocument();
expect(screen.queryByRole("heading", { name: "AI工程" })).not.toBeInTheDocument();
```

- [ ] **Step 2: Run focused renderer tests to verify they fail**

Run: `pnpm --dir packages/web test -- daily-brief ai-briefs`  
Run: `uv run pytest packages/ai-brief/tests/test_composer.py -q -p no:cacheprovider`  
Expected: FAIL because the TypeScript schema accepts only version 1 and templates derive titles only from theme labels.

- [ ] **Step 3: Implement version-specific rendering**

In `ai-briefs.ts`, accept `z.union([z.literal(1), z.literal(2)]).default(1)`. Make `moduleLabels` derive the visible list by version so v2 summaries cannot include AI工程.

In `daily-brief.tsx`, create the digest section list with the version branch below; filter only null sections afterward:

```tsx
const digestSections = content.version === 2
  ? [
      { slotId: "today-ai", title: "一、今日AI", section: content.today_ai },
      { slotId: "ai-masters", title: "二、AI大神", section: content.ai_masters },
      { slotId: "ai-research", title: "三、AI研究", section: content.ai_research },
      { slotId: "agent-tools", title: "四、Agent工具", section: content.agent_tools },
    ]
  : legacyDigestSections;
```

In both Jinja templates, change the digest-section macro to receive a title parameter. Pass v2's exact numbered titles only when `brief.version == 2`; keep the current theme-label calls and engineering formatting branch for v1. For v2, never pass `brief.ai_engineering` to either template.

- [ ] **Step 4: Run focused renderer tests**

Run: `pnpm --dir packages/web test -- daily-brief ai-briefs`  
Run: `uv run pytest packages/ai-brief/tests/test_composer.py -q -p no:cacheprovider`  
Expected: PASS for both v1 compatibility and v2 four-module output.

- [ ] **Step 5: Commit the renderer change**

```bash
git add packages/web/lib/ai-briefs.ts \
  packages/web/components/daily-brief.tsx \
  packages/web/components/daily-brief.test.tsx \
  packages/web/lib/ai-briefs.test.ts \
  packages/ai-brief/ai_brief/templates/ai_brief.html.j2 \
  packages/ai-brief/ai_brief/templates/ai_brief.txt.j2 \
  packages/ai-brief/tests/test_composer.py
git commit -m "feat(web): render four-module AI daily v2"
```

## Task 4: End-to-end no-send verification and release readiness

**Files:**
- Modify only if a failing test exposes a direct requirement gap in the files named by Tasks 1-3.
- Test: `packages/ai-brief/tests/`
- Test: `packages/web/components/daily-brief.test.tsx`
- Test: `packages/web/lib/ai-briefs.test.ts`

**Interfaces:**
- Consumes: production runtime `.env` with `AI_EMAIL_SEND_ENABLED=false`.
- Produces: an `awaiting_approval` v2 run only when the five-item regional quota passes; no release or Resend delivery in this verification.

- [ ] **Step 1: Run the complete Python and web test suites**

Run:

```bash
export UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache
uv run pytest packages/ai-brief/tests -q -p no:cacheprovider
uv run ruff check packages/ai-brief
MYPYPATH=packages/shared uv run mypy packages/ai-brief/ai_brief
pnpm --dir packages/web test
```

Expected: all tests pass; existing documented integration skips may remain skipped; no new lint or type errors.

- [ ] **Step 2: Run a no-send v2 workflow verification**

Add a `test_workflow.py` fixture that supplies a v2 `DigestBundle` with five Today AI stories labelled three overseas/two domestic and the three other required modules. Patch `composer.compose_for_date` and the delivery boundary, then verify generation reaches `awaiting_approval` without either collaborator being called.

```python
assert result.status == "awaiting_approval"
compose.assert_not_called()
deliver.assert_not_called()
assert saved_content["version"] == 2
assert [story["label"] for story in saved_content["today_ai"]["stories"]] == [
    "海外新闻", "海外新闻", "海外新闻", "国内新闻", "国内新闻"
]
```

Run: `uv run pytest packages/ai-brief/tests/test_workflow.py -q -p no:cacheprovider`  
Expected: PASS with no SMTP, Resend, or production release call.

- [ ] **Step 3: Verify a quota-shortage date fails closed without delivery**

Use the deterministic fixture/test adapter rather than a production mailbox. Assert the run status is `blocked`, approval/release reject it, and `deliveries=[]`.

```python
assert result.status == "blocked"
assert result.exit_code == 1
assert deliveries_for_date(connection, brief_date) == []
```

- [ ] **Step 4: Review the diff and commit any direct test-only correction**

Run: `git diff --check && git status --short`  
Expected: only files required by Tasks 1-3 and any direct test correction are present. Do not stage `ops/launchd/run-ai-generate.sh`, `ops/launchd/run-ai-release.sh`, or `ops/launchd/run-daily.sh`.

- [ ] **Step 5: Request review before production publication**

Dispatch a code reviewer with the diff from the first implementation commit through the final verification commit. Require review of: v1/v2 compatibility, exact regional quota, fail-closed release path, and all three render targets. Resolve every Critical or Important finding, rerun the affected tests, then ask the user for explicit authorization before pushing, deployment, or sending any production emails.

## Plan Self-Review

- **Spec coverage:** Task 1 implements five-item regional selection and normalized labels. Task 2 implements v2 persistence, removes future engineering requirements, and fail-closed quota validation. Task 3 preserves v1 and renders v2 identically across web and both email formats. Task 4 validates no-send behavior and production authorization boundaries.
- **Placeholder scan:** The plan has no incomplete implementation markers, deferred implementation notes, or operator-supplied command arguments.
- **Type consistency:** `_select_today_ai_items` consumes and returns `list[EventItem]`; `DigestBundle.today_ai` remains `DigestSection | None`; Python and Zod both accept content versions `1 | 2` with version 1 as the legacy default.

