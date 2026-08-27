# AIVIZENS Phase 2 Real Content Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every mock AI article with database-backed, full daily archives while ensuring only explicitly published briefs are public.

**Architecture:** Add publication workflow columns to `ai_daily_briefs`, then centralize server-only reads in `lib/ai-briefs.ts`. The homepage renders the latest six published issues and `/daily/[date]` renders one complete validated `AiBriefContent` document. Preview access remains separate and is implemented in Phase 3.

**Tech Stack:** Next.js 14 App Router, React Server Components, TypeScript, Zod, Vitest, Supabase/Postgres, Next Metadata and ImageResponse.

## Global Constraints

- Public reads always include `status='published'`; a date alone is never authorization.
- Existing historical AI briefs are preserved but are not made public automatically.
- The homepage contains no fabricated stories or dead “阅读全文” links.
- The archive path is exactly `/daily/YYYY-MM-DD`; no per-story route is introduced.
- Keep the approved “100,000+ readers” trust bar, company logos, and current `href="#"` social entries.
- Every source URL rendered from stored content must be `https:` or be omitted.
- Unpublished dates return 404 and are absent from sitemap/metadata.

---

### Task 1: Add the publication workflow schema

**Files:**
- Create: `infra/supabase/migrations/0012_ai_brief_workflow.sql`
- Modify: `infra/supabase/all_migrations.sql`
- Create: `packages/ai-brief/tests/test_brief_status.py`
- Modify: `packages/ai-brief/ai_brief/storage.py`

**Interfaces:**
- `BriefStatus = Literal["generating", "blocked", "awaiting_approval", "approved", "published"]`.
- `fetch_public_brief(conn, brief_date)` returns content only for `published`.
- `list_public_briefs(conn, limit)` returns newest published briefs.

- [ ] **Step 1: Write failing storage tests**

Add tests showing that public fetch/list exclude `generating`, `blocked`, `awaiting_approval`, and `approved`, and include only `published`. Assert an existing approved/published row cannot be overwritten by `upsert_daily_brief`.

- [ ] **Step 2: Run the focused tests**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_brief_status.py -q
```

Expected before implementation: missing status-aware functions.

- [ ] **Step 3: Add the additive migration**

Add:

```sql
ALTER TABLE ai_daily_briefs
  ADD COLUMN status text NOT NULL DEFAULT 'generating'
    CHECK (status IN ('generating','blocked','awaiting_approval','approved','published')),
  ADD COLUMN quality_report jsonb,
  ADD COLUMN digest_sources jsonb,
  ADD COLUMN approved_at timestamptz,
  ADD COLUMN published_at timestamptz,
  ADD COLUMN failure_reason text;

CREATE INDEX idx_ai_daily_briefs_public
  ON ai_daily_briefs(published_at DESC)
  WHERE status = 'published';
```

Backfill existing rows to `awaiting_approval`, with a `quality_report` warning identifying them as pre-workflow imports. Do not mark them published automatically.

- [ ] **Step 4: Implement status-aware storage**

Add a Python `BriefStatus` type, public fetch/list functions, and an upsert condition that permits regeneration only from `generating`, `blocked`, or `awaiting_approval`. Return an explicit conflict result for `approved` and `published` rows.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest -c pyproject.toml packages/ai-brief/tests/test_brief_status.py -q
git add infra/supabase packages/ai-brief/ai_brief/storage.py packages/ai-brief/tests/test_brief_status.py
git commit -m "feat(content): add brief publication states"
```

### Task 2: Create a typed public brief query layer

**Files:**
- Create: `packages/web/lib/ai-briefs.ts`
- Create: `packages/web/lib/ai-briefs.test.ts`
- Modify: `packages/web/lib/briefs.ts`

**Interfaces:**
- `AiBriefSummary { briefDate, subject, preheader, editorial, modules, publishedAt }`.
- `AiPublishedBrief { briefDate, content, publishedAt }`.
- `listPublishedBriefs(limit = 6): Promise<AiBriefSummary[]>`.
- `getPublishedBrief(date: string): Promise<AiPublishedBrief | null>`.
- `getPublishedNeighbors(date: string): Promise<{ previous: string | null; next: string | null }>`.
- `isBriefDate(value: string): boolean` validates canonical `YYYY-MM-DD` and a real calendar date.

- [ ] **Step 1: Write failing query and validation tests**

Mock Supabase and assert every public query applies `.eq("status", "published")`. Cover invalid dates, malformed JSON content, empty optional modules, ordering, a six-item limit, and previous/next date selection.

- [ ] **Step 2: Run the tests**

```bash
npm --workspace @nev/web test -- lib/ai-briefs.test.ts
```

- [ ] **Step 3: Implement schema parsing and safe projections**

Define a Zod schema that matches the current Python `AiBriefContent` JSON, including optional `ai_masters`, `ai_research`, `ai_engineering`, `agent_tools`, images, and source URLs. Reject a whole unpublished/invalid brief rather than rendering untrusted partial data. Filter non-HTTPS optional links at the projection boundary.

- [ ] **Step 4: Consolidate site URL behavior**

Move AIVIZENS `siteBaseUrl()` into the new module or a neutral `site-url.ts`; keep `briefs.ts` only until NEV removal in Phase 4. The canonical production fallback is `https://aivizens.com`.

- [ ] **Step 5: Verify and commit**

```bash
npm --workspace @nev/web test -- lib/ai-briefs.test.ts
npm --workspace @nev/web run typecheck
git add packages/web/lib/ai-briefs.ts packages/web/lib/ai-briefs.test.ts packages/web/lib/briefs.ts
git commit -m "feat(web): add published brief query layer"
```

### Task 3: Replace the mock homepage grid

**Files:**
- Create: `packages/web/components/latest-briefs-grid.tsx`
- Create: `packages/web/components/latest-briefs-grid.test.tsx`
- Modify: `packages/web/app/page.tsx`
- Delete: `packages/web/components/latest-posts-grid.tsx`
- Delete: `packages/web/lib/mock-ai-posts.ts`

**Interfaces:**
- `LatestBriefsGrid({ briefs }: { briefs: AiBriefSummary[] })` is a presentational server-compatible component.
- Each card links to `/daily/${brief.briefDate}`.

- [ ] **Step 1: Write failing component tests**

Assert six issue cards render real dates, subjects, editorials, module labels, and valid archive links. Assert the empty state explains that the first issue is being prepared and still displays the subscription CTA.

- [ ] **Step 2: Run the focused test**

```bash
npm --workspace @nev/web test -- components/latest-briefs-grid.test.tsx
```

- [ ] **Step 3: Implement the real issue grid**

Use deterministic visual accents derived from module names, not fabricated cover art. Rename the section to “最新日报”. Render only values from `AiBriefSummary` and preserve semantic `<article>`, `<time>`, and link elements.

- [ ] **Step 4: Make the homepage fetch published issues**

Convert `AiTrendsHome` to `async`, call `listPublishedBriefs(6)`, and pass the result to `LatestBriefsGrid`. Preserve the hero, both subscription entrypoints, trust bar, company logos, and footer/social behavior approved by the user.

- [ ] **Step 5: Delete mocks, verify, and commit**

```bash
rg -n "MOCK_AI_POSTS|getMockPosts|gpt-6-release|latest-posts-grid" packages/web
npm --workspace @nev/web test -- components/latest-briefs-grid.test.tsx
npm --workspace @nev/web run build
git add packages/web/app/page.tsx packages/web/components packages/web/lib/mock-ai-posts.ts
git commit -m "feat(web): show real daily briefs on homepage"
```

Expected `rg`: no matches after deletion.

### Task 4: Build the full daily archive page

**Files:**
- Create: `packages/web/app/daily/[date]/page.tsx`
- Create: `packages/web/app/daily/[date]/daily-page.test.tsx`
- Create: `packages/web/components/daily-brief.tsx`
- Create: `packages/web/components/daily-brief.test.tsx`
- Create: `packages/web/components/brief-subscribe-cta.tsx`

**Interfaces:**
- `generateMetadata({ params })` returns canonical, title, description, and OG URL only for a published date.
- `DailyBrief({ brief })` renders the complete stored issue without model calls or data mutation.
- Invalid or unpublished dates call `notFound()`.

- [ ] **Step 1: Write failing page tests**

Cover all five sections, missing optional section, images with alt text, HTTPS source links, published date/read time, previous/next navigation, subscription CTA, invalid date, and unpublished date.

- [ ] **Step 2: Run and observe failure**

```bash
npm --workspace @nev/web test -- 'app/daily/[date]/daily-page.test.tsx' components/daily-brief.test.tsx
```

- [ ] **Step 3: Implement the reusable full-issue renderer**

Render subject, editorial, intro bullets, `today_ai`, `ai_masters`, `ai_research`, `ai_engineering`, `agent_tools`, sources, images, and `yesterday_top` when present. Derive read time from rendered plain-text length with a documented Chinese reading-rate constant.

- [ ] **Step 4: Implement the route and navigation**

Validate `params.date`, fetch only published content, fetch published neighbors, set `dynamic = "force-dynamic"` or a documented cache/revalidation policy, and call `notFound()` for all non-public cases.

- [ ] **Step 5: Verify and commit**

```bash
npm --workspace @nev/web test -- 'app/daily/[date]/daily-page.test.tsx' components/daily-brief.test.tsx
npm --workspace @nev/web run build
git add packages/web/app/daily packages/web/components/daily-brief.tsx packages/web/components/daily-brief.test.tsx packages/web/components/brief-subscribe-cta.tsx
git commit -m "feat(web): publish full daily archive pages"
```

### Task 5: Add archive metadata, OpenGraph, robots, and sitemap

**Files:**
- Create: `packages/web/app/daily/[date]/opengraph-image.tsx`
- Create: `packages/web/app/daily/[date]/opengraph-image.test.tsx`
- Modify: `packages/web/app/layout.tsx`
- Modify: `packages/web/app/robots.ts`
- Modify: `packages/web/app/sitemap.ts`
- Create: `packages/web/app/sitemap.test.ts`

**Interfaces:**
- Sitemap contains `/` plus published `/daily/YYYY-MM-DD` rows only.
- OG generation reads the same `getPublishedBrief` interface as the page.
- Robots allows public archives and excludes preview/confirmation operational URLs.

- [ ] **Step 1: Write failing metadata tests**

Assert unpublished rows never enter sitemap or OG responses, canonical URLs use `https://aivizens.com`, and `/confirm`, `/unsubscribe`, `/rate`, `/api`, and the future `/preview` are not indexed.

- [ ] **Step 2: Implement metadata and OG**

Use the existing bundled OG font helpers. Render AIVIZENS branding, date, subject, and editorial only; do not load arbitrary remote images during OG generation.

- [ ] **Step 3: Replace the NEV sitemap query**

Query `ai_daily_briefs` with `status='published'`, order by `published_at DESC`, and produce `/daily/${brief_date}` entries. Remove `/nev` entries.

- [ ] **Step 4: Verify and commit**

```bash
npm --workspace @nev/web test -- app/sitemap.test.ts 'app/daily/[date]/opengraph-image.test.tsx'
npm --workspace @nev/web run build
git add packages/web/app/layout.tsx packages/web/app/robots.ts packages/web/app/sitemap.ts packages/web/app/sitemap.test.ts 'packages/web/app/daily/[date]/opengraph-image.tsx' 'packages/web/app/daily/[date]/opengraph-image.test.tsx'
git commit -m "feat(web): add AIVIZENS archive SEO"
```

### Task 6: Add browser acceptance coverage

**Files:**
- Create: `packages/web/e2e/daily-archive.spec.ts`
- Create: `packages/web/test/fixtures/published-brief.ts`
- Modify: `.github/workflows/test.yml`

- [ ] **Step 1: Seed one published and one awaiting-approval fixture**

The published fixture must cover all content modules; the awaiting fixture must have a distinct date and secret phrase.

- [ ] **Step 2: Write the browser test**

Assert the homepage links to the published date, the full archive renders, metadata/canonical values are correct, the awaiting date returns 404, and the awaiting secret phrase never appears on public pages.

- [ ] **Step 3: Run the phase gate**

```bash
make verify
npm --workspace @nev/web run test:e2e -- daily-archive.spec.ts
rg -n "MOCK_AI_POSTS|getMockPosts|gpt-6-release" packages/web
```

Expected `rg`: no output.

- [ ] **Step 4: Commit**

```bash
git add packages/web/e2e/daily-archive.spec.ts packages/web/test/fixtures/published-brief.ts .github/workflows/test.yml
git commit -m "test(web): cover public daily archives"
```

## Phase 2 Gate

```bash
make verify
npm --workspace @nev/web run test:e2e -- daily-archive.spec.ts
```

Expected: the homepage and sitemap contain only real published briefs; `/daily/YYYY-MM-DD` renders the complete issue; unpublished content returns 404; no mock story remains. Do not start Phase 3 until this gate passes.
