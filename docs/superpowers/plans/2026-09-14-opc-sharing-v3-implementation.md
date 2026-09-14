# AIVIZENS OPC Sharing V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a required OPC case to every new AIVIZENS daily brief, normalize and compare case revenue as USD monthly revenue, render the same frozen V3 content on the website and in email, and perform one controlled 2026-09-14 backfill.

**Architecture:** Extend the frozen JSONB content contract to V3 with a dedicated `OpcCase`, add a fifth exact-date Gmail digest adapter input, and keep parsing, currency normalization, case selection, image binding, editorial assembly, and rendering in focused units. Normal generation remains fail-closed through the existing quality gate; the already-published 2026-09-14 row is revised only by a temporary hash-guarded operator script after the deployed code passes all checks.

**Tech Stack:** Python 3.12+, Pydantic 2, selectolax, Decimal, httpx, Pillow, psycopg 3, Jinja2, Next.js 15, React, TypeScript, Zod, Vitest, Supabase/PostgreSQL, Resend, Gmail IMAP.

**Spec:** `docs/superpowers/specs/2026-09-14-opc-sharing-v3-design.md`

## Global Constraints

- New automatically generated briefs use `version: 3`; V1 and V2 remain readable and keep their existing layout and numbering.
- OPC mail must match sender `paul.fan.2200@gmail.com` and exact subject date `ai-opc-sharing YYYY-MM-DD`; no cross-date fallback is allowed.
- A valid OPC source contains exactly two complete cases; both revenues must normalize to USD monthly revenue before selection.
- ARR is divided by 12; non-USD currency uses the latest available ECB workday reference rate; ambiguous or unavailable conversion blocks publication.
- The selected case N uses case N's image only. A missing, invalid, blank, transparent, or failed upload blocks publication.
- V3 has five required modules and exactly four intro bullets; the fourth bullet is `🧰 ` plus the first Agent工具 headline.
- Website reading time is always `5 分钟阅读`; email retains its current five-minute text and personalized greeting.
- AI工程 remains absent from V2 and V3.
- Automated tests never read real Gmail, call ECB, upload images, access production Supabase, or send Resend email.
- The 2026-09-14 backfill updates the website and sends exactly one test email to `gito.fan@163.com`; it does not rewrite historical `ai_deliveries` or email other subscribers.
- Do not stage or modify the existing untracked `.codex/`, `output/`, or `tmp/` directories.

---

## File Structure

### New production files

- `packages/ai-brief/ai_brief/digest/opc_parser.py` — pure HTML-to-`OpcCaseCandidate` parser.
- `packages/ai-brief/ai_brief/digest/exchange_rates.py` — pure revenue normalization plus isolated ECB HTTP/XML adapter.

### New test files and fixtures

- `packages/ai-brief/tests/fixtures/opc_sharing_2026-09-14.html` — sanitized real OPC email HTML.
- `packages/ai-brief/tests/fixtures/ecb_daily_rates.xml` — minimal deterministic ECB-format fixture.
- `packages/ai-brief/tests/test_opc_parser.py` — case and revenue parsing tests.
- `packages/ai-brief/tests/test_exchange_rates.py` — currency conversion, formatting, and ECB adapter tests.

### Existing files modified by responsibility

- `packages/ai-brief/ai_brief/schema.py` and `packages/web/lib/ai-briefs.ts` — shared V3 frozen-content contract.
- `packages/ai-brief/ai_brief/digest/models.py` — transport-neutral OPC intermediate types.
- `packages/ai-brief/ai_brief/config.py`, `digest/input.py`, and `digest/gmail_input.py` — fifth exact-date source.
- `packages/ai-brief/ai_brief/digest/generate.py` and `ai_brief/runner.py` — OPC construction, image binding, editorial, four bullets, and V3 assembly.
- `packages/ai-brief/ai_brief/quality.py` and `ai_brief/storage.py` — fail-closed V3 checks and privacy-safe run metadata.
- `packages/ai-brief/ai_brief/templates/ai_brief.html.j2` and `ai_brief.txt.j2` — V3 email layout.
- `packages/web/components/daily-brief.tsx` — V3 website layout and fixed read time.
- Existing test helpers in `packages/ai-brief/tests/` and `packages/web/` — complete V3 fixtures and regression coverage.

---

### Task 1: Add the V3 Frozen Content Contract

**Files:**
- Modify: `packages/ai-brief/ai_brief/schema.py`
- Modify: `packages/ai-brief/tests/test_schema.py`
- Modify: `packages/web/lib/ai-briefs.ts`
- Modify: `packages/web/lib/ai-briefs.test.ts`

**Interfaces:**
- Produces: Python `OpcCase` and TypeScript/Zod `OpcCaseSchema` with identical fields.
- Produces: `AiBriefContent.version: 1 | 2 | 3` and `opc_case: OpcCase | null`.
- Consumes: no new interfaces.

- [ ] **Step 1: Write Python schema tests that distinguish V2 from V3**

Import `OpcCase`, add the following helpers, and assert V3 accepts the OPC value while V3 without it fails validation:

```python
def _opc_case() -> OpcCase:
    return OpcCase(
        sharer="Ruslan",
        headline="$8M 产品一夜归零，Zipchat 再冲到 $2M ARR",
        summary="他重建电商 AI 销售代理并恢复增长。",
        original_revenue="$167K MRR",
        monthly_revenue_usd=167_000,
        revenue_display="$167K 美元月度营收",
        url="https://www.indiehackers.com/post/example",
        header_image="https://cdn.example.com/opc.png",
        header_image_alt="Ruslan 的 Zipchat 案例",
    )


def _v2_contract_brief() -> AiBriefContent:
    return AiBriefContent(
        version=2,
        brief_date="2026-09-14",
        subject="AI 日报",
        preheader="今天最值得关注的 AI 动态",
        editorial="今天的核心判断。",
        intro_bullets=["要点一"],
    )


def test_v3_requires_a_complete_opc_case() -> None:
    valid = _v2_contract_brief().model_copy(
        update={"version": 3, "opc_case": _opc_case(), "intro_bullets": ["一", "二", "三", "🧰 工具"]}
    )
    assert AiBriefContent.model_validate(valid.model_dump()).version == 3

    with pytest.raises(ValidationError):
        AiBriefContent.model_validate(
            valid.model_dump(exclude={"opc_case"})
        )


def test_v2_remains_valid_without_opc_case() -> None:
    brief = _v2_contract_brief().model_copy(update={"version": 2, "opc_case": None})
    assert AiBriefContent.model_validate(brief.model_dump()).opc_case is None
```

- [ ] **Step 2: Run the Python tests and verify RED**

Run:

```bash
uv run pytest packages/ai-brief/tests/test_schema.py -q
```

Expected: collection or assertion failure because `OpcCase`, V3, and `opc_case` do not exist.

- [ ] **Step 3: Implement the minimal Python contract**

Add:

```python
class OpcCase(BaseModel):
    sharer: str = Field(min_length=1, max_length=80)
    headline: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    original_revenue: str = Field(min_length=1, max_length=80)
    monthly_revenue_usd: int = Field(gt=0)
    revenue_display: str = Field(min_length=1, max_length=80)
    url: str
    header_image: str
    header_image_alt: str = Field(min_length=1, max_length=160)
```

Change the version annotation to `Literal[1, 2, 3]`, add `opc_case: OpcCase | None = None`, and extend the existing legacy-content validator so V2 and V3 both clear AI工程 and legacy auxiliary fields while V3 raises `ValueError("v3 content requires opc_case")` when OPC is absent.

- [ ] **Step 4: Add the matching Zod RED test**

In `packages/web/lib/ai-briefs.test.ts`, build a complete V3 content object with the same literal fields and assert `AiBriefContentSchema.safeParse` succeeds; delete `opc_case` and assert it fails.

- [ ] **Step 5: Run the Web contract test and verify RED**

Run:

```bash
npm test --workspace @nev/web -- lib/ai-briefs.test.ts
```

Expected: FAIL because version 3 and `opc_case` are not accepted.

- [ ] **Step 6: Implement the matching Zod contract**

Add a strict `OpcCaseSchema` with positive integer `monthly_revenue_usd`, HTTPS validation for `url` and `header_image`, extend the version union to 3, add nullable `opc_case`, and add a V3 `superRefine` issue when it is absent. Preserve existing V2 checks.

- [ ] **Step 7: Run both contract suites and verify GREEN**

Run:

```bash
uv run pytest packages/ai-brief/tests/test_schema.py -q
npm test --workspace @nev/web -- lib/ai-briefs.test.ts
```

Expected: both commands pass.

- [ ] **Step 8: Commit Task 1**

```bash
git add packages/ai-brief/ai_brief/schema.py packages/ai-brief/tests/test_schema.py packages/web/lib/ai-briefs.ts packages/web/lib/ai-briefs.test.ts
git commit -m "feat(content): add V3 OPC case contract"
```

---

### Task 2: Parse OPC Cases and Revenue Fields

**Files:**
- Create: `packages/ai-brief/ai_brief/digest/opc_parser.py`
- Create: `packages/ai-brief/tests/fixtures/opc_sharing_2026-09-14.html`
- Create: `packages/ai-brief/tests/test_opc_parser.py`
- Modify: `packages/ai-brief/ai_brief/digest/models.py`

**Interfaces:**
- Produces: `Revenue(amount: Decimal, currency: str, period: Literal["MRR", "ARR"], raw: str)`.
- Produces: `OpcCaseCandidate(index: int, sharer: str, headline: str, body: str, revenue: Revenue, url: str)`.
- Produces: `parse_opc_digest(html: str) -> list[OpcCaseCandidate]`.
- Consumes: the exact HTML source contract documented in the spec.

- [ ] **Step 1: Save a sanitized structural fixture derived from the verified mail**

Create the fixture with the verified tag order, sharers, revenues, and selected-case URL while keeping unrelated prose sanitized:

```html
<html><body>
  <h3>案例 1 · Aurélien：案例一主题</h3>
  <p>案例一的去敏正文。</p>
  <p><strong>收入：</strong>$83K+ MRR</p>
  <p>🔗 <a href="https://www.indiehackers.com/post/sanitized-aurelien-case">阅读原文</a></p>
  <hr>
  <h3>案例 2 · Ruslan：$8M 产品一夜归零，Zipchat 再冲到 $2M ARR</h3>
  <p>他重建电商 AI 销售代理并恢复增长。</p>
  <p><strong>收入：</strong>$167K MRR</p>
  <p>🔗 <a href="https://www.indiehackers.com/post/UZm68xNgjDZBHH7Mvc54">阅读原文</a></p>
</body></html>
```

- [ ] **Step 2: Write parser RED tests**

Define `FIXTURE = Path(__file__).parent / "fixtures/opc_sharing_2026-09-14.html"`, then cover the fixture and malformed variants:

```python
def test_parses_two_real_opc_cases() -> None:
    cases = parse_opc_digest(FIXTURE.read_text(encoding="utf-8"))
    assert [(case.index, case.sharer) for case in cases] == [(1, "Aurélien"), (2, "Ruslan")]
    assert cases[0].revenue == Revenue(Decimal("83000"), "USD", "MRR", "$83K+ MRR")
    assert cases[1].revenue == Revenue(Decimal("167000"), "USD", "MRR", "$167K MRR")
    assert cases[1].url == "https://www.indiehackers.com/post/UZm68xNgjDZBHH7Mvc54"


@pytest.mark.parametrize(
    "revenue_text",
    ["¥100K MRR", "$100K", "100K MRR", "$many MRR"],
)
def test_rejects_ambiguous_or_incomplete_revenue(revenue_text: str) -> None:
    assert parse_revenue(revenue_text) is None
```

Also assert missing sharer, body, revenue, HTTPS link, or duplicate case index excludes that candidate.

- [ ] **Step 3: Run parser tests and verify RED**

Run:

```bash
uv run pytest packages/ai-brief/tests/test_opc_parser.py -q
```

Expected: collection failure because the new module and types do not exist.

- [ ] **Step 4: Implement pure parsing**

Use `selectolax.parser.HTMLParser`. Iterate `h3` siblings until the next `h3`, parse `案例 N · sharer：headline`, take the first non-income body paragraph, the paragraph containing `收入`, and the first HTTPS anchor. Use `Decimal`, expand `K/M/B` to `1_000/1_000_000/1_000_000_000`, and map explicit currency tokens from the spec. Return only complete candidates and sort by `index`.

- [ ] **Step 5: Run parser tests and verify GREEN**

```bash
uv run pytest packages/ai-brief/tests/test_opc_parser.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add packages/ai-brief/ai_brief/digest/models.py packages/ai-brief/ai_brief/digest/opc_parser.py packages/ai-brief/tests/fixtures/opc_sharing_2026-09-14.html packages/ai-brief/tests/test_opc_parser.py
git commit -m "feat(opc): parse daily sharing cases"
```

---

### Task 3: Normalize Revenue with ECB Rates

**Files:**
- Create: `packages/ai-brief/ai_brief/digest/exchange_rates.py`
- Create: `packages/ai-brief/tests/fixtures/ecb_daily_rates.xml`
- Create: `packages/ai-brief/tests/test_exchange_rates.py`

**Interfaces:**
- Consumes: `Revenue` and `OpcCaseCandidate` from Task 2.
- Produces: `fetch_ecb_rates() -> dict[str, Decimal]` including `EUR: Decimal("1")`.
- Produces: `monthly_revenue_usd(revenue: Revenue, rates: Mapping[str, Decimal]) -> Decimal`.
- Produces: `SelectedOpcCase(candidate: OpcCaseCandidate, monthly_revenue_usd: Decimal, revenue_display: str, converted: bool)`.
- Produces: `select_highest_case(cases: Sequence[OpcCaseCandidate], rates_loader: Callable[[], Mapping[str, Decimal]]) -> SelectedOpcCase`.
- Produces: `format_monthly_usd(amount: Decimal, *, approximate: bool) -> str`.

- [ ] **Step 1: Write conversion and selection RED tests**

Use literal hand-calculated rates where 1 EUR = 1.20 USD and 1 EUR = 7.20 CNY:

```python
RATES = {"EUR": Decimal("1"), "USD": Decimal("1.20"), "CNY": Decimal("7.20")}


def usd_cases() -> list[OpcCaseCandidate]:
    return [
        OpcCaseCandidate(
            index=1,
            sharer="Aurélien",
            headline="案例一主题",
            body="案例一正文",
            revenue=Revenue(Decimal("83000"), "USD", "MRR", "$83K+ MRR"),
            url="https://www.indiehackers.com/post/case-one",
        ),
        OpcCaseCandidate(
            index=2,
            sharer="Ruslan",
            headline="Zipchat 再冲到 $2M ARR",
            body="案例二正文",
            revenue=Revenue(Decimal("167000"), "USD", "MRR", "$167K MRR"),
            url="https://www.indiehackers.com/post/case-two",
        ),
    ]


def test_arr_is_converted_to_monthly_usd() -> None:
    revenue = Revenue(Decimal("1200000"), "USD", "ARR", "$1.2M ARR")
    assert monthly_revenue_usd(revenue, RATES) == Decimal("100000")


def test_cny_mrr_uses_euro_cross_rate() -> None:
    revenue = Revenue(Decimal("720000"), "CNY", "MRR", "CNY 720K MRR")
    assert monthly_revenue_usd(revenue, RATES) == Decimal("120000")


def test_selects_case_two_and_does_not_fetch_rates_for_usd() -> None:
    loader = Mock(side_effect=AssertionError("USD selection must not fetch ECB"))
    selected = select_highest_case(usd_cases(), loader)
    assert selected.candidate.index == 2
    assert selected.monthly_revenue_usd == Decimal("167000")
    assert selected.revenue_display == "$167K 美元月度营收"
    loader.assert_not_called()
```

Also cover equal revenue selecting index 1, unknown currency, missing ECB currency, zero rate, and `约 $120K 美元月度营收` for converted values.

- [ ] **Step 2: Run conversion tests and verify RED**

```bash
uv run pytest packages/ai-brief/tests/test_exchange_rates.py -q
```

Expected: collection failure because `exchange_rates.py` does not exist.

- [ ] **Step 3: Implement pure Decimal conversion and formatting**

Use this formula and reject missing/non-positive rates:

```python
period_amount = revenue.amount / Decimal(12) if revenue.period == "ARR" else revenue.amount
usd_amount = (
    period_amount
    if revenue.currency == "USD"
    else period_amount / rates[revenue.currency] * rates["USD"]
)
return usd_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
```

Selection must require exactly two cases, load ECB only if at least one source currency is not USD, and use `(monthly_revenue_usd, -index)` so equal amounts select case 1.

- [ ] **Step 4: Add the ECB adapter RED test**

Mock `httpx.get` with the checked-in XML fixture. Assert the request uses the official daily XML URL, a 10-second timeout, and returns exact Decimal rates for USD, CNY, and EUR. Add failure tests for HTTP 500 and malformed XML.

- [ ] **Step 5: Implement the isolated ECB adapter**

Set:

```python
ECB_DAILY_RATES_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
```

Fetch with `httpx.get(..., timeout=10.0, follow_redirects=True)`, call `raise_for_status()`, parse XML using `xml.etree.ElementTree`, return finite positive Decimal rates, and raise `RevenueConversionError` for network, HTTP, XML, or required-rate failures. Do not add another package dependency.

- [ ] **Step 6: Run exchange tests and verify GREEN**

```bash
uv run pytest packages/ai-brief/tests/test_exchange_rates.py -q
```

Expected: PASS with no live network access.

- [ ] **Step 7: Commit Task 3**

```bash
git add packages/ai-brief/ai_brief/digest/exchange_rates.py packages/ai-brief/tests/fixtures/ecb_daily_rates.xml packages/ai-brief/tests/test_exchange_rates.py
git commit -m "feat(opc): normalize monthly revenue"
```

---

### Task 4: Fetch and Build the OPC Module

**Files:**
- Modify: `packages/ai-brief/ai_brief/config.py`
- Modify: `packages/ai-brief/ai_brief/digest/input.py`
- Modify: `packages/ai-brief/ai_brief/digest/gmail_input.py`
- Modify: `packages/ai-brief/ai_brief/digest/generate.py`
- Modify: `packages/ai-brief/ai_brief/digest/condenser.py`
- Modify: `packages/ai-brief/ai_brief/runner.py`
- Modify: `packages/ai-brief/tests/test_digest_input.py`
- Modify: `packages/ai-brief/tests/test_digest_logic.py`
- Modify: `packages/ai-brief/tests/test_workflow.py`

**Interfaces:**
- Consumes: Task 1 `OpcCase`; Task 2 parser; Task 3 selection and formatter.
- Produces: `build_opc_case(brief_date: str, digest: DigestEnvelope | None, rates_loader: Callable[[], Mapping[str, Decimal]] = fetch_ecb_rates) -> tuple[OpcCase | None, int]`.
- Produces: `build_editorial(editorial: str, opc_case: OpcCase) -> str`.
- Produces: `DigestBundle.opc_case`, `DigestBundle.opc_candidate_count`, and V3 payload assembly.

- [ ] **Step 1: Write Gmail input RED tests**

Extend the existing exact-date mapping test to assert the keys are exactly `events`, `builder`, `opc`, `research`, `agent`. Add a test that the OPC fetcher receives prefix `ai-opc-sharing`, date `2026-08-04`, and is called only once when absent.

- [ ] **Step 2: Run the input tests and verify RED**

```bash
uv run pytest packages/ai-brief/tests/test_digest_input.py -q
```

Expected: FAIL because `DigestKind` and prefix mapping omit `opc`.

- [ ] **Step 3: Add the exact-date OPC input**

Add `"opc"` to `DigestKind`, define `DIGEST_OPC_SUBJECT_PREFIX = "ai-opc-sharing"`, add it to `_SUBJECT_PREFIXES`, and keep it out of `_FALLBACK_KINDS`.

- [ ] **Step 4: Write OPC image-binding and assembly RED tests**

Construct an OPC envelope with `case1.jpg` and `case2.png`. Patch uploader and assert the selected case 2 uploads bytes from `case2.png`, never calls Qwen, and produces:

```python
assert result.sharer == "Ruslan"
assert result.monthly_revenue_usd == 167_000
assert result.revenue_display == "$167K 美元月度营收"
assert result.header_image == "https://cdn.example.com/opc-case.png"
assert candidate_count == 2
```

Add strict tests for one parsed case, missing selected attachment, invalid selected image, and positional fallback only when exactly two valid image attachments exist.

- [ ] **Step 5: Run the digest logic tests and verify RED**

```bash
uv run pytest packages/ai-brief/tests/test_digest_logic.py -q
```

Expected: FAIL because `build_opc_case` does not exist.

- [ ] **Step 6: Implement deterministic OPC construction**

In `generate.py`, parse exactly two cases, call `select_highest_case`, resolve the matching attachment, reuse `_is_usable_header_image` and `_find_hero_band`, upload under module path `opc-case`, and return a frozen `OpcCase`. Return `(None, parsed_count)` when parsing or revenue selection is invalid. When the selected attachment is absent or unusable, retain the selected case with `header_image=""` so the quality gate emits `opc_image_missing` and stores an auditable blocked candidate; never substitute the other case's image. Let upload/network exceptions reach the existing durable failure handler.

- [ ] **Step 7: Write editorial and intro RED tests**

Assert:

```python
assert build_editorial(
    "安全叙事成为资本变量。与此同时，旧的后半段。",
    opc_case,
) == "安全叙事成为资本变量。今日给大家分享一个来自“Ruslan”的“Zipchat 再冲到 $2M ARR”OPC案例。"
```

Also assert an editorial without `与此同时，` retains its concise lead, and a long lead is clipped at a sentence boundary while the entire OPC recommendation remains present and the final value is at most 220 characters. Build a bundle with three model bullets and Agent工具 first headline `spec-kit — 规范先行的 AI 编码流程`; assert the stored V3 bullets equal the three originals plus `🧰 spec-kit — 规范先行的 AI 编码流程`.

- [ ] **Step 8: Run workflow tests and verify RED**

```bash
uv run pytest packages/ai-brief/tests/test_workflow.py -q
```

Expected: FAIL because the runner still writes version 2 and does not assemble OPC/editorial/four bullets.

- [ ] **Step 9: Assemble V3 in the normal generator**

Build OPC alongside the four existing modules. Update the TodayAI prompt to require exactly three intro bullets and a concise editorial lead. Implement the deterministic editorial with the existing sentence-boundary clipper and the schema's 220-character limit:

```python
def build_editorial(editorial: str, opc_case: OpcCase) -> str:
    lead = editorial.partition("与此同时，")[0].strip()
    recommendation = (
        f"今日给大家分享一个来自“{opc_case.sharer}”的"
        f"“{opc_case.headline}”OPC案例。"
    )
    if len(recommendation) > 220:
        raise ValueError("OPC recommendation exceeds editorial limit")
    room = max(0, 220 - len(recommendation))
    clipped_lead = condenser._clip_sentence(lead, room).strip() if room else ""
    return f"{clipped_lead}{recommendation}"
```

In `_build_brief_without_lookup`, write `version: 3`, `opc_case`, the deterministic editorial, and exactly four bullets. Call `build_editorial` only when `bundle.opc_case` exists; otherwise preserve the model lead so schema and quality can return a structured OPC blocker. Append the Agent headline only when `agent_tools.stories[0]` exists. Include OPC in `_module_count`. In `_digest_sources`, set `parse_count = bundle.opc_candidate_count` when `kind == "opc"`; retain section story counts for the other four kinds, so adding the fifth source cannot index the old section map and crash. If the model produces fewer or more than three bullets, preserve the count so the quality gate blocks instead of silently slicing it into apparent validity.

- [ ] **Step 10: Run input, digest, and workflow suites and verify GREEN**

```bash
uv run pytest packages/ai-brief/tests/test_digest_input.py packages/ai-brief/tests/test_digest_logic.py packages/ai-brief/tests/test_workflow.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit Task 4**

```bash
git add packages/ai-brief/ai_brief/config.py packages/ai-brief/ai_brief/digest/input.py packages/ai-brief/ai_brief/digest/gmail_input.py packages/ai-brief/ai_brief/digest/generate.py packages/ai-brief/ai_brief/digest/condenser.py packages/ai-brief/ai_brief/runner.py packages/ai-brief/tests/test_digest_input.py packages/ai-brief/tests/test_digest_logic.py packages/ai-brief/tests/test_workflow.py
git commit -m "feat(pipeline): build required OPC sharing module"
```

---

### Task 5: Enforce V3 Quality and Safe Run Metadata

**Files:**
- Modify: `packages/ai-brief/ai_brief/schema.py`
- Modify: `packages/ai-brief/ai_brief/quality.py`
- Modify: `packages/ai-brief/ai_brief/storage.py`
- Modify: `packages/ai-brief/ai_brief/runner.py`
- Modify: `packages/ai-brief/tests/test_quality.py`
- Modify: `packages/ai-brief/tests/test_digest_run_storage.py`
- Modify: `packages/ai-brief/tests/test_storage.py`
- Modify: `packages/ai-brief/tests/test_workflow.py`

**Interfaces:**
- Consumes: V3 bundle and `opc` envelope from Task 4.
- Produces: issue codes `opc_case_missing`, `opc_candidate_count_invalid`, `opc_image_missing`, `intro_bullet_count_invalid`, and `intro_agent_topic_mismatch`.
- Produces: metrics `opc_candidate_count`, `opc_case_count`, `opc_monthly_revenue_usd`, and `opc_freshness_hours`.
- Produces: `validate_brief(..., opc_candidate_count: int | None = None) -> QualityReport`.

- [ ] **Step 1: Write fail-closed quality RED tests**

Import `OpcCase`, add a valid V3 fixture and exact-date OPC digest, then mutate one invariant at a time:

```python
def _v3_brief() -> AiBriefContent:
    agent_tools = _valid_brief().agent_tools
    assert agent_tools is not None
    return _v2_brief().model_copy(
        update={
            "version": 3,
            "opc_case": OpcCase(
                sharer="Ruslan",
                headline="Zipchat 再冲到 $2M ARR",
                summary="案例二正文",
                original_revenue="$167K MRR",
                monthly_revenue_usd=167_000,
                revenue_display="$167K 美元月度营收",
                url="https://www.indiehackers.com/post/case-two",
                header_image="https://aivizens.com/images/opc.png",
                header_image_alt="Ruslan 的 Zipchat 案例",
            ),
            "intro_bullets": [
                "Models improve",
                "Tools mature",
                "Agents ship",
                f"🧰 {agent_tools.stories[0].headline}",
            ],
        }
    )


def _fresh_v3_digests() -> dict[DigestKind, DigestEnvelope | None]:
    digests = _fresh_v2_digests()
    digests["opc"] = _envelope(
        "opc",
        source_urls=("https://www.indiehackers.com/post/case-two",),
    )
    return digests


def test_v3_blocks_missing_opc_case() -> None:
    brief = _v3_brief().model_copy(update={"opc_case": None})
    report = _report(brief, _fresh_v3_digests(), opc_candidate_count=2)
    assert any(i.code == "opc_case_missing" and i.path == "opc_case" for i in report.blockers)


def test_v3_blocks_wrong_candidate_count() -> None:
    report = _report(_v3_brief(), _fresh_v3_digests(), opc_candidate_count=1)
    assert any(i.code == "opc_candidate_count_invalid" and i.path == "digests.opc" for i in report.blockers)


def test_v3_blocks_missing_opc_image() -> None:
    brief = _v3_brief()
    assert brief.opc_case is not None
    brief = brief.model_copy(
        update={"opc_case": brief.opc_case.model_copy(update={"header_image": ""})}
    )
    report = _report(brief, _fresh_v3_digests(), opc_candidate_count=2)
    assert any(i.code == "opc_image_missing" and i.path == "opc_case.header_image" for i in report.blockers)


def test_v3_blocks_intro_that_does_not_match_agent_headline() -> None:
    brief = _v3_brief().model_copy(update={"intro_bullets": ["一", "二", "三", "🧰 错误工具"]})
    report = _report(brief, _fresh_v3_digests(), opc_candidate_count=2)
    assert any(i.code == "intro_agent_topic_mismatch" and i.path == "intro_bullets" for i in report.blockers)
```

Update `_envelope` and its URL mapping to accept `opc`. Also assert missing/stale `digests.opc` uses `required_digest_stale`, three bullets use `intro_bullet_count_invalid`, V2 remains valid without OPC, V3 retains the V2 three-overseas/two-domestic TodayAI quota, and `indiehackers.com` is a known source domain.

- [ ] **Step 2: Run quality tests and verify RED**

```bash
uv run pytest packages/ai-brief/tests/test_quality.py -q
```

Expected: FAIL because OPC paths, codes, metrics, and required-source logic are absent.

- [ ] **Step 3: Implement V3 quality rules**

Extend the allowlisted issue codes, metric keys, `opc_case` paths, digest kinds, freshness metric map, known domains, and summary checks. Add keyword-only `opc_candidate_count: int | None = None` to `validate_brief` and pass `bundle.opc_candidate_count` from the runner. For V3, require `opc`, `events`, `builder`, `research`, and `agent`; treat OPC as a primary 24-hour exact-date source and require `matched_date == brief_date` with no fallback. Require `opc_candidate_count == 2`, one frozen OPC case, a non-empty HTTPS header image, exactly four intro bullets, fourth bullet exactly `🧰 {first Agent工具 headline}`, the existing five-story three-overseas/two-domestic TodayAI quota, and all five modules. Validate `opc_case.url` with `_url_problem` and require the exact URL to appear in the trusted OPC envelope, reporting the existing URL blocker codes on `opc_case.url`. Populate the four OPC metrics from the validated frozen case and exact-date envelope.

- [ ] **Step 4: Write persistence RED tests**

Assert `finish_digest_run` retains only safe OPC metadata and numeric metrics while dropping raw HTML, attachment bytes, exchange response bodies, and unknown keys. Assert V3 normalization preserves `opc_case` and continues clearing legacy fields.

- [ ] **Step 5: Run storage tests and verify RED**

```bash
uv run pytest packages/ai-brief/tests/test_digest_run_storage.py packages/ai-brief/tests/test_storage.py -q
```

Expected: FAIL because existing allowlists and `_normalize_v2_content` do not cover V3 OPC.

- [ ] **Step 6: Implement safe V3 persistence**

Rename `_normalize_v2_content` to `_normalize_current_content`, normalize both versions 2 and 3 through `AiBriefContent`, and extend only the explicit metadata/metric allowlists required by the tests. Do not persist Gmail body content, image bytes, exchange XML, credentials, or unsubscribe data.

- [ ] **Step 7: Add a PostgreSQL V3 publish-without-send acceptance test**

Extend `_seed_generated_brief` with an optional `content` argument, then add this integration test using the existing subscriber, cleanup, approval, and release helpers:

```python
@pytest.mark.integration
def test_postgres_v3_publishes_but_does_not_send_when_email_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief_date = date(2096, 9, 14)
    email = "opc-v3-disabled-send@example.test"
    monkeypatch.setenv("AI_EMAIL_SEND_ENABLED", "false")
    conn = _postgres_connection()
    try:
        _cleanup_workflow_fixtures(conn, [brief_date], [email])
        _insert_active_subscriber(conn, email)
        v3 = AiBriefContent(
            version=3,
            brief_date=brief_date.isoformat(),
            subject="Frozen V3 candidate",
            preheader="OPC acceptance",
            editorial="核心判断。今日给大家分享一个来自“Ruslan”的“Zipchat”OPC案例。",
            intro_bullets=["一", "二", "三", "🧰 Agent 0"],
            opc_case=OpcCase(
                sharer="Ruslan",
                headline="Zipchat",
                summary="案例正文",
                original_revenue="$167K MRR",
                monthly_revenue_usd=167_000,
                revenue_display="$167K 美元月度营收",
                url="https://www.indiehackers.com/post/case-two",
                header_image="https://aivizens.com/images/opc.png",
                header_image_alt="Zipchat 案例",
            ),
            today_ai=_section(Theme.MODEL_RESEARCH),
            ai_masters=_section(Theme.PRODUCT_TOOLS),
            ai_research=_section(Theme.AI_RESEARCH),
            ai_engineering=None,
            agent_tools=_section(Theme.AGENT_TOOLS, header_image=None),
            model="integration-model",
        ).model_dump(mode="json")
        _seed_generated_brief(conn, brief_date, passed=True, content=v3)
        assert runner.approve_brief(
            conn, brief_date, approved_by="integration-operator"
        ).changed
        released = runner.release_approved(conn, brief_date, only_email=email)
        result = deliverer.send_pending(conn, brief_date=brief_date)

        assert (released.status, released.released, released.composed) == (
            "published",
            True,
            1,
        )
        assert (result.attempted, result.sent, result.failed) == (0, 0, 0)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, count(*) FROM ai_deliveries "
                "WHERE brief_date = %s GROUP BY status;",
                (brief_date,),
            )
            assert cur.fetchone() == ("pending", 1)
    finally:
        _cleanup_workflow_fixtures(conn, [brief_date], [email])
        conn.close()
```

Import `ai_brief.deliverer as deliverer` and `OpcCase`. The test proves release can publish frozen V3 content and queue one delivery while the disabled transport sends nothing.

- [ ] **Step 8: Run quality, storage, and workflow suites and verify GREEN**

```bash
uv run pytest packages/ai-brief/tests/test_quality.py packages/ai-brief/tests/test_digest_run_storage.py packages/ai-brief/tests/test_storage.py packages/ai-brief/tests/test_workflow.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 5**

```bash
git add packages/ai-brief/ai_brief/schema.py packages/ai-brief/ai_brief/quality.py packages/ai-brief/ai_brief/storage.py packages/ai-brief/ai_brief/runner.py packages/ai-brief/tests/test_quality.py packages/ai-brief/tests/test_digest_run_storage.py packages/ai-brief/tests/test_storage.py packages/ai-brief/tests/test_workflow.py
git commit -m "feat(quality): require complete V3 OPC content"
```

---

### Task 6: Render V3 Email Content

**Files:**
- Modify: `packages/ai-brief/ai_brief/templates/ai_brief.html.j2`
- Modify: `packages/ai-brief/ai_brief/templates/ai_brief.txt.j2`
- Modify: `packages/ai-brief/tests/test_composer.py`

**Interfaces:**
- Consumes: frozen `AiBriefContent.opc_case` from Task 1.
- Produces: HTML and plain-text email ordering and copy for V3.

- [ ] **Step 1: Write V3 email RED tests**

Render a complete V3 fixture and assert:

```python
for fragment in (
    "OPC分享",
    "一、OPC案例",
    "二、今日AI",
    "三、AI大神",
    "四、AI研究",
    "五、Agent工具",
    "Ruslan",
    "$167K 美元月度营收",
    "阅读原文",
):
    assert fragment in html
    assert fragment in text

assert html.index("OPC分享") < html.index("今日精选") < html.index("工具学习")
assert text.index("OPC分享") < text.index("今日精选") < text.index("工具学习")
```

Assert the OPC image URL and source URL are present, exactly four intro bullets render, email still contains personalized greeting and `5 分钟阅读`, and V2 output keeps its old four module numbers.

- [ ] **Step 2: Run composer tests and verify RED**

```bash
uv run pytest packages/ai-brief/tests/test_composer.py -q
```

Expected: FAIL because the templates omit OPC and use V2 numbering for all current content.

- [ ] **Step 3: Add a dedicated OPC email macro and V3 branches**

The HTML macro must render, in order, sharer label, full-width header image, headline, summary, revenue, and source link inside the existing two-pixel black rounded border. Add the black `OPC分享` section header before 今日精选; retain visual spacing with the existing CSS `letter-spacing` rather than inserting spaces into the text. Use V3 module titles `二/三/四/五`; retain existing V2 branches.

The text template must render the same fields and order without HTML markup. Do not move the unsubscribe footer or rating links.

- [ ] **Step 4: Run composer tests and verify GREEN**

```bash
uv run pytest packages/ai-brief/tests/test_composer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 6**

```bash
git add packages/ai-brief/ai_brief/templates/ai_brief.html.j2 packages/ai-brief/ai_brief/templates/ai_brief.txt.j2 packages/ai-brief/tests/test_composer.py
git commit -m "feat(email): render OPC sharing V3 brief"
```

---

### Task 7: Render V3 Website Content

**Files:**
- Modify: `packages/web/components/daily-brief.tsx`
- Modify: `packages/web/components/daily-brief.test.tsx`
- Modify: `packages/web/lib/ai-briefs.ts`
- Modify: `packages/web/lib/ai-briefs.test.ts`
- Modify: `packages/web/test/fixtures/published-brief.ts`
- Modify: `packages/web/test/fixtures/published-brief.test.ts`

**Interfaces:**
- Consumes: TypeScript `AiBriefContent` and `OpcCase` from Task 1.
- Produces: V3 website layout, fixed reading time, fixed bold greeting, and archive module label.

- [ ] **Step 1: Write website RED tests**

Create a complete V3 fixture and assert:

```tsx
expect(screen.getByText("5 分钟阅读")).toBeInTheDocument();
expect(
  screen.getByText(
    "早上好，AI科技爱好者们！以下是今天最值得关注的 AI 洞察，5 分钟带你看懂全局。",
  ),
).toHaveClass("font-bold");

for (const title of [
  "OPC分享",
  "一、OPC案例",
  "二、今日AI",
  "三、AI大神",
  "四、AI研究",
  "五、Agent工具",
]) {
  expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
}
```

Assert the OPC section has `border-2 border-gray-900`, its image is responsive and cropped, sharer/revenue/source URL render, all four intro bullets render, and heading DOM order matches the spec. Add a V2 fixture assertion that it does not show OPC and retains `一、今日AI` through `四、Agent工具`.

- [ ] **Step 2: Run component tests and verify RED**

```bash
npm test --workspace @nev/web -- components/daily-brief.test.tsx
```

Expected: FAIL because the website still computes reading time and has no V3 OPC rendering.

- [ ] **Step 3: Implement the minimal V3 website renderer**

Add a focused `OpcBlock` component. For every version, render literal `5 分钟阅读`; remove the now-unused reading-time calculation helpers and their direct tests. Add the fixed bold website greeting immediately below the main title, keep stored editorial below it, insert `OPC分享` before 今日精选 for V3, and branch the numbered digest section list by version.

- [ ] **Step 4: Add archive projection RED coverage**

In `ai-briefs.test.ts`, assert a V3 summary with `opc_case` returns module labels `OPC案例`, `今日AI`, `AI大神`, `AI研究`, `Agent工具` in that order.

- [ ] **Step 5: Update archive projection and fixtures**

Include `opc_case && "OPC案例"` before the four V3 module labels without changing V1/V2 projections. Upgrade only the dedicated V3 fixture; leave legacy fixtures intact.

- [ ] **Step 6: Run all affected Web tests and verify GREEN**

```bash
npm test --workspace @nev/web -- components/daily-brief.test.tsx lib/ai-briefs.test.ts test/fixtures/published-brief.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit Task 7**

```bash
git add packages/web/components/daily-brief.tsx packages/web/components/daily-brief.test.tsx packages/web/lib/ai-briefs.ts packages/web/lib/ai-briefs.test.ts packages/web/test/fixtures/published-brief.ts packages/web/test/fixtures/published-brief.test.ts
git commit -m "feat(web): render OPC sharing V3 brief"
```

---

### Task 8: Run Cross-Layer and Full Verification

**Files:**
- Modify only when a failing test reveals a V3 fixture that must be completed: `packages/ai-brief/tests/` or `packages/web/`
- Do not modify production code for unrelated existing warnings.

**Interfaces:**
- Consumes: all Tasks 1–7.
- Produces: a fully green branch ready for PR.

- [ ] **Step 1: Run all AI brief tests**

```bash
uv run pytest packages/ai-brief/tests -q
```

Expected: all AI brief tests pass. If an old fixture is intentionally V2, keep it V2 rather than adding fake OPC data.

- [ ] **Step 2: Run the complete Web suite**

```bash
npm test --workspace @nev/web
npm run typecheck --workspace @nev/web
npm run build --workspace @nev/web
```

Expected: all tests pass, TypeScript exits 0, and Next production build succeeds.

- [ ] **Step 3: Run the V3 PostgreSQL acceptance in a disposable shadow database**

Start a dedicated PostgreSQL 16 container, wait for readiness, and apply the exact CI migration list:

```bash
docker run --rm --name nev-opc-v3-postgres -e POSTGRES_USER=nev -e POSTGRES_PASSWORD=nev_local_dev -e POSTGRES_DB=nev_brief -p 55439:5432 -d postgres:16-alpine
for i in {1..30}; do docker exec nev-opc-v3-postgres pg_isready -U nev -d nev_brief && break; sleep 1; done
while IFS= read -r migration; do docker exec -i nev-opc-v3-postgres psql -U nev -d nev_brief --set=ON_ERROR_STOP=on < "$migration" || exit 1; done < <(uv run python scripts/ci/list_postgres_test_migrations.py)
DATABASE_URL=postgresql://nev:nev_local_dev@127.0.0.1:55439/nev_brief SUPABASE_URL=https://example.invalid SUPABASE_SERVICE_ROLE_KEY=integration-test-service-role DEEPSEEK_API_KEY=integration-test-deepseek RESEND_API_KEY=integration-test-resend AI_EMAIL_SEND_ENABLED=false make test-integration
docker stop nev-opc-v3-postgres
```

Expected: the integration suite passes, including `test_postgres_v3_publishes_but_does_not_send_when_email_is_disabled`; no Resend request is made. If a command fails, collect its output before stopping the container and fix only the V3-related cause.

- [ ] **Step 4: Run the repository verification gate**

```bash
env SUPABASE_URL=https://example.supabase.co SUPABASE_SERVICE_ROLE_KEY=test-service-role RESEND_API_KEY=re_test DEEPSEEK_API_KEY=test-deepseek FEISHU_WEBHOOK_URL= AI_EMAIL_SEND_ENABLED=false HEALTHCHECKS_PING_URL= SENTRY_DSN= make verify
```

Expected baseline: Python tests, Web tests, Ruff, strict mypy, TypeScript, lint, and production build all exit 0. Existing documented deprecation and `<img>` warnings may remain; no new warning is accepted.

- [ ] **Step 5: Inspect the exact diff**

```bash
git diff --check main...HEAD
git status --short
git diff --stat main...HEAD
```

Expected: no whitespace errors; only planned files are tracked; `.codex/`, `output/`, and `tmp/` remain unstaged.

- [ ] **Step 6: Commit any test-only fixture completion**

Run this commit only if Step 1 or Step 2 required intentional fixture changes not already committed:

```bash
git add packages/ai-brief/tests packages/web
git commit -m "test(opc): complete V3 acceptance coverage"
```

- [ ] **Step 7: Request an independent code review**

Invoke `superpowers:requesting-code-review` against `main...HEAD` and give the reviewer the approved spec plus this plan. Require review of schema parity, strict failure paths, attachment-to-case binding, currency arithmetic, privacy-safe metadata, V1/V2 compatibility, email non-delivery in tests, and the backfill guard. Resolve every P1/P2 finding, rerun the affected focused tests plus `make verify`, and commit only the necessary corrections before proceeding.

---

### Task 9: Merge, Deploy, and Perform the Controlled 2026-09-14 Backfill

**Files:**
- Create temporarily, never commit: `/private/tmp/aivizens-opc-v3-backfill-2026-09-14.py`
- Create temporarily, mode 0600: `/private/tmp/aivizens-opc-v3-backup-2026-09-14.json`
- Do not modify source files during the production operation.

**Interfaces:**
- Consumes: deployed V3 code and production credentials from `/Users/jack/nev-brief/.env`.
- Produces: merged `main`, Vercel production deployment, synchronized Mac Mini checkout, revised 2026-09-14 website content, and one idempotent test email.

- [ ] **Step 1: Push and open a PR**

Create `/private/tmp/aivizens-opc-v3-pr.md` with `apply_patch` using this exact body:

```markdown
## Summary
- add the exact-date OPC Gmail source and deterministic two-case parser
- normalize revenue to USD monthly revenue with Decimal and ECB reference rates
- freeze the selected case and its matching image in the V3 content contract
- enforce strict V3 quality, freshness, privacy, and four-bullet rules
- render OPC sharing and five numbered modules in website and email
- keep V1/V2 rendering compatible and AI engineering absent from V2/V3
- prepare a guarded 2026-09-14 website backfill and one-recipient validation email

## Safety
- missing, ambiguous, stale, or incomplete OPC input blocks publication
- automated tests do not access Gmail, ECB, production Supabase, image storage, or Resend
- the historical backfill is not exposed as a general production CLI

## Verification
- `make verify`
- disposable PostgreSQL 16 integration suite with email sending disabled
- independent review against the approved V3 spec
```

Then run:

```bash
git push -u origin codex/opc-sharing-v3
gh pr create --base main --head codex/opc-sharing-v3 --title "feat(ai): add OPC sharing V3 daily brief" --body-file /private/tmp/aivizens-opc-v3-pr.md
```

- [ ] **Step 2: Wait for every required GitHub check**

```bash
gh pr checks --watch --interval 10
```

Expected: unit, integration, and web acceptance all pass. The repository's automatic GitHub-to-Vercel deployment is intentionally disconnected, so do not require a Vercel Preview check. Do not merge while any required GitHub check is pending or failed.

- [ ] **Step 3: Merge and verify the remote main commit**

```bash
gh pr merge --merge
git switch main
git pull --ff-only
git rev-parse HEAD
```

Expected: PR state is merged and local `main` equals `origin/main`.

- [ ] **Step 4: Synchronize the Mac Mini production checkout**

Run:

```bash
git -C /Users/jack/nev-brief -c core.fileMode=false pull --ff-only
git -C /Users/jack/nev-brief rev-parse HEAD
stat -f '%Sp %N' /Users/jack/nev-brief/ops/launchd/run-ai-generate.sh
```

Expected: Mac Mini equals the merge commit and the active AIVIZENS launchd runner remains executable.

- [ ] **Step 5: Deploy Vercel production explicitly with the configured token**

Because automatic GitHub deployment is disconnected, deploy from the synchronized production checkout. Load `/Users/jack/nev-brief/.env`, confirm the token authenticates, explicitly link the existing `nev-brief` project, and deploy production:

```bash
set -a
source /Users/jack/nev-brief/.env
set +a
NODE_USE_ENV_PROXY=1 npx vercel@latest whoami --token "$VERCEL_TOKEN"
NODE_USE_ENV_PROXY=1 npx vercel@latest link --yes --project nev-brief --token "$VERCEL_TOKEN"
NODE_USE_ENV_PROXY=1 npx vercel@latest deploy --prod --yes --token "$VERCEL_TOKEN"
```

Expected: authentication succeeds, the linked project is `nev-brief`, and the deployment reaches `Ready`. Verify the returned production deployment and `https://www.aivizens.com/` both return HTTP 200 before touching the 2026-09-14 row. Never print or persist the token outside `.env` and Vercel's local link metadata.

- [ ] **Step 6: Build the temporary dry-run backfill tool**

Use `apply_patch` to create `/private/tmp/aivizens-opc-v3-backfill-2026-09-14.py`. It must:

1. Read the published 2026-09-14 row and active test subscriber inside read transactions.
2. Fetch all five exact-date digest envelopes with fallback disabled.
3. Preserve the existing subject, preheader, four module bodies, and first three intro bullets.
4. Build only the new OPC case, append the Agent工具 headline, and replace the editorial tail.
5. Validate the V3 schema and quality report with email sending disabled.
6. Compute SHA-256 over canonical old and new JSON.
7. Write the old content, model, source run id, digest metadata, quality report, and hashes to the mode-0600 backup path.
8. Print only date, selected case index, sharer, normalized revenue, attachment filename, blocker codes, and hashes; never print credentials, email bodies, tokens, or image bytes.
9. Require `--apply` before any forward database mutation, `--rollback` before a guarded restore, and `--send-test` before Resend.

- [ ] **Step 7: Run the 2026-09-14 dry run with sending disabled**

```bash
set -a
source /Users/jack/nev-brief/.env
set +a
export AI_EMAIL_SEND_ENABLED=false
export AIVIZENS_OPERATOR_ID=opc-v3-backfill
PYTHONPATH=/Users/jack/nev-brief/packages/ai-brief:/Users/jack/nev-brief/packages/shared /Users/jack/nev-brief/.venv/bin/python /private/tmp/aivizens-opc-v3-backfill-2026-09-14.py
```

Expected: selected case 2, sharer Ruslan, monthly USD revenue 167000, attachment `case2.png`, zero blockers, and no database or email mutation.

- [ ] **Step 8: Apply one content-guarded database transaction**

The temporary script's `--apply` path must lock the row, recompute and compare the canonical old SHA-256 recorded by the dry run, create a new audit run, execute this guarded update, and finish that run as `completed` within one transaction:

```sql
UPDATE ai_daily_briefs
SET content = %(new_content)s::jsonb,
    model = %(model)s,
    quality_report = %(quality_report)s::jsonb,
    digest_sources = %(digest_sources)s::jsonb,
    source_run_id = %(run_id)s,
    updated_at = statement_timestamp()
WHERE brief_date = DATE '2026-09-14'
  AND status = 'published'
  AND content = %(expected_old_content)s::jsonb
RETURNING id;
```

Require exactly one returned row; otherwise roll back. Keep `published_at`, `status`, and every `ai_deliveries` row unchanged.

Run:

```bash
PYTHONPATH=/Users/jack/nev-brief/packages/ai-brief:/Users/jack/nev-brief/packages/shared /Users/jack/nev-brief/.venv/bin/python /private/tmp/aivizens-opc-v3-backfill-2026-09-14.py --apply
```

- [ ] **Step 9: Verify the production website before email**

```bash
curl -L -sS -o /private/tmp/aivizens-2026-09-14-opc.html -w 'HTTP=%{http_code}\n' 'https://www.aivizens.com/daily/2026-09-14?opc-v3-check=1'
```

Expected: HTTP 200 and server-rendered output contains `OPC分享`, `一、OPC案例`, `Ruslan`, `$167K 美元月度营收`, the Indie Hackers source URL, and module titles two through five in order. The image URL must return HTTP 200 with an image content type.

If any website assertion fails, do not send email. Run the script's `--rollback` path; it must require the current content to equal the backed-up new JSON, restore old content/model/quality/digest/source-run fields without changing `published_at`, and return exactly one row. Then verify the old SHA-256 is restored and investigate before attempting a new apply.

- [ ] **Step 10: Send exactly one idempotent test email**

Set `AI_EMAIL_SEND_ENABLED=true` only for this command. The temporary script must load the active subscriber's real unsubscribe token, render through `composer.render`, and call `resend_client.send_email` with:

```text
to = gito.fan@163.com
idempotency_key = opc-v3-backfill-2026-09-14-gito-fan-163
```

Run:

```bash
export AI_EMAIL_SEND_ENABLED=true
PYTHONPATH=/Users/jack/nev-brief/packages/ai-brief:/Users/jack/nev-brief/packages/shared /Users/jack/nev-brief/.venv/bin/python /private/tmp/aivizens-opc-v3-backfill-2026-09-14.py --send-test
export AI_EMAIL_SEND_ENABLED=false
```

Expected: one Resend email id, no new or reset 2026-09-14 delivery row, and no other recipient.

- [ ] **Step 11: Verify the next scheduled run configuration**

```bash
launchctl print gui/$(id -u)/com.aivizens.ai-generate
plutil -extract StartCalendarInterval xml1 -o - /Users/jack/Library/LaunchAgents/com.aivizens.ai-generate.plist
tail -n 80 /Users/jack/nev-brief/logs/ai-generate-$(TZ=Asia/Shanghai date +%Y%m%d).log
```

Expected: the single caffeinated `com.aivizens.ai-generate` cycle remains loaded at 08:10, 09:10, and 10:10; its path points to the synchronized production checkout; there is no separate release agent dependency; and `/Users/jack/nev-brief/.env` retains its configured email sending state.

- [ ] **Step 12: Report final evidence**

Report the PR URL, merge SHA, complete local and GitHub test counts, Vercel production status, Mac Mini SHA, 2026-09-14 old/new content hashes, selected OPC case and image, live page checks, Resend id, recipient count one, and next launchd schedule. Do not include credentials, unsubscribe tokens, raw email bodies, or attachment bytes.
