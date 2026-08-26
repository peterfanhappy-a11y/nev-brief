# Digest Parser Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the email-first digest pipeline parse the current `ai-events` and `ai-research` HTML while preserving the existing legacy fixture formats.

**Architecture:** Extend each pure parser with a narrow fallback for the current upstream markup. Keep the existing selectors and output models unchanged; only add alternate extraction when the legacy shape yields no items. Verify against checked-in representative HTML fixtures before running the full generation flow.

**Tech Stack:** Python 3, selectolax, pytest, existing `EventItem` and `ResearchPaper` dataclasses, local PostgreSQL shadow run.

## Global Constraints

- Use the existing sender/recipient architecture: read from Peter's mailbox and keep Paul as the digest sender.
- Do not enable email delivery during verification (`AI_EMAIL_SEND_ENABLED=false`).
- Do not change production Supabase or Resend configuration.
- Preserve parsing of the existing legacy fixtures.
- Keep URL extraction HTTPS-only as enforced by downstream quality rules.

---

### Task 1: Add regression fixtures and failing parser tests

**Files:**
- Create: `packages/ai-brief/tests/fixtures/events_digest_2026-08-16.html`
- Create: `packages/ai-brief/tests/fixtures/research_digest_2026-08-16.html`
- Modify: `packages/ai-brief/tests/test_digest_parsers.py`

**Interfaces:**
- Tests consume `parse_events_digest` and `parse_research_digest` without network access.
- Fixtures contain the current email body shape, with only representative content and no credentials.

- [x] **Step 1: Add sanitized current-format fixtures**

Copy the already observed HTML structure into small fixtures: events use a heading followed by repeated styled blocks containing a source/label line, an `h2` headline, summary paragraph, and source link; research uses repeated `h2` paper headings, takeaways, and HTTPS links directly under the body.

- [x] **Step 2: Write failing tests**

Add tests that require at least three events with category/value/source/body/url fields and at least two research papers with source tags, titles, takeaways, and HTTPS URLs. Import `parse_research_digest` and assert the current fixtures produce non-empty results.

- [x] **Step 3: Run the focused tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest -c pyproject.toml packages/ai-brief/tests/test_digest_parsers.py -q
```

Expected: the new current-format event and research assertions fail while the existing legacy tests pass.

### Task 2: Support current events HTML without changing legacy behavior

**Files:**
- Modify: `packages/ai-brief/ai_brief/digest/events_parser.py`
- Test: `packages/ai-brief/tests/test_digest_parsers.py`

**Interfaces:**
- `parse_events_digest(html: str) -> list[EventItem]` remains unchanged.

- [x] **Step 1: Implement the smallest current-format fallback**

If `div.item` produced no items, iterate current event blocks identified by their contained `h2` headline. Derive category/value/source from the preceding label line, use the nearest summary paragraph as body, select the first HTTPS link as URL, and assign the numeric prefix from the headline or encounter order. Return the same `EventItem` model and skip entries without a headline or valid HTTPS URL.

- [x] **Step 2: Run event tests GREEN**

Run:

```bash
UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest -c pyproject.toml packages/ai-brief/tests/test_digest_parsers.py -k events -q
```

Expected: all event tests, including the original legacy fixture tests, pass.

### Task 3: Support current research HTML without changing legacy behavior

**Files:**
- Modify: `packages/ai-brief/ai_brief/digest/research_parser.py`
- Test: `packages/ai-brief/tests/test_digest_parsers.py`

**Interfaces:**
- `parse_research_digest(html: str) -> list[ResearchPaper]` remains unchanged.

- [x] **Step 1: Implement a direct-body fallback**

Keep the existing parent-`div` extraction first. When no papers are found, treat each `h2` as a paper heading, collect following sibling paragraphs until the next `h2`, remove the `Link:` paragraph from takeaways, select its first HTTPS link, and preserve the `[Arxiv]`/`[HuggingFace]` source tag parsing.

- [x] **Step 2: Run research tests GREEN**

Run:

```bash
UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache uv run pytest -c pyproject.toml packages/ai-brief/tests/test_digest_parsers.py -k research -q
```

Expected: current and legacy research parsing tests pass.

### Task 4: Full verification and local no-send generation

**Files:**
- No additional production files unless a focused test exposes a parser regression.

- [x] **Step 1: Run parser and AI brief regression suites**

Run `pytest` for all `packages/ai-brief/tests`, then Ruff and strict mypy using the repository's existing commands.

- [x] **Step 2: Run the local shadow generation**

Source only `/Users/jack/nev-brief/.env`, override `DATABASE_URL` to the local PostgreSQL on port `55448`, clear Feishu/Healthchecks/Sentry endpoints, set `AI_EMAIL_SEND_ENABLED=false`, and run `python -m ai_brief generate --date 2026-08-16`.

- [x] **Step 3: Verify safety and outcome**

Confirm the run records all five source emails, does not create deliveries, and either passes quality or reports only the remaining external dependency blockers (Qwen/uploader/LLM). Do not run a real release or send command.

- [x] **Step 4: Commit the focused change**

Use a commit message such as `fix(digest): parse current email html` after `git diff --check` and the verification gates pass.
