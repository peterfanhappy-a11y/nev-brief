import { expect, test } from "@playwright/test";

import {
  AWAITING_BRIEF_DATE,
  AWAITING_SECRET,
  DAILY_ARCHIVE_FIXTURE_ROWS,
  PUBLISHED_BRIEF_CONTENT,
  PUBLISHED_BRIEF_DATE,
} from "@/test/fixtures/published-brief";

const supabaseUrl = process.env.SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

test.beforeAll(async ({ request }) => {
  expect(supabaseUrl).toBeTruthy();
  expect(serviceRoleKey).toBeTruthy();

  const response = await request.post(
    `${supabaseUrl}/rest/v1/ai_daily_briefs?on_conflict=brief_date`,
    {
      headers: {
        apikey: serviceRoleKey!,
        authorization: `Bearer ${serviceRoleKey}`,
        prefer: "resolution=merge-duplicates,return=minimal",
      },
      data: DAILY_ARCHIVE_FIXTURE_ROWS,
    },
  );

  expect([200, 201]).toContain(response.status());
});

test("homepage exposes only the published daily issue", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.locator(`a[href="/daily/${PUBLISHED_BRIEF_DATE}"]`),
  ).toBeVisible();
  await expect(page.getByText(PUBLISHED_BRIEF_CONTENT.subject)).toBeVisible();
  await expect(
    page.locator(`a[href="/daily/${AWAITING_BRIEF_DATE}"]`),
  ).toHaveCount(0);
  await expect(page.getByText(AWAITING_SECRET)).toHaveCount(0);
});

test("published archive renders complete content and public metadata", async ({
  page,
}) => {
  await page.goto(`/daily/${PUBLISHED_BRIEF_DATE}`);

  await expect(
    page.getByRole("heading", { name: PUBLISHED_BRIEF_CONTENT.subject }),
  ).toBeVisible();
  for (const heading of [
    "今日AI",
    "AI大神",
    "AI研究",
    "AI工程",
    "Agent工具",
    "更多精选",
    "AI工具",
    "每日技巧",
    "快讯",
    "昨日焦点",
  ]) {
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
  }
  for (const text of [
    "今日AI Fixture 新闻",
    "AI大神 Fixture 新闻",
    "AI研究 Fixture 新闻",
    "AI工程 Fixture 新闻",
    "Agent工具 Fixture 新闻",
    "Legacy 精选 Fixture",
    "Fixture AI Tool",
    "Fixture 每日技巧",
    "Fixture 快讯",
    "Fixture 昨日热门",
  ]) {
    await expect(page.getByText(text, { exact: true })).toBeVisible();
  }
  await expect(page.getByRole("navigation", { name: "日报期数导航" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: /免费订阅 AIVIZENS/ }),
  ).toBeVisible();

  const publicTitle = `${PUBLISHED_BRIEF_CONTENT.subject} · AIVIZENS 日报`;
  await expect(page).toHaveTitle(publicTitle);
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    "content",
    PUBLISHED_BRIEF_CONTENT.preheader,
  );
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute(
    "content",
    publicTitle,
  );
  await expect(page.locator('meta[property="og:description"]')).toHaveAttribute(
    "content",
    PUBLISHED_BRIEF_CONTENT.preheader,
  );
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    new RegExp(`/daily/${PUBLISHED_BRIEF_DATE}$`),
  );
  await expect(page.getByText(AWAITING_SECRET)).toHaveCount(0);
});

test("sitemap contains only the published fixture date", async ({ request }) => {
  const response = await request.get("/sitemap.xml");
  expect(response.status()).toBe(200);
  const sitemap = await response.text();

  expect(sitemap).toContain(`/daily/${PUBLISHED_BRIEF_DATE}`);
  expect(sitemap).not.toContain(`/daily/${AWAITING_BRIEF_DATE}`);
  expect(sitemap).not.toContain(AWAITING_SECRET);
});

test("awaiting-approval fixture is a real public 404", async ({ page }) => {
  const response = await page.goto(`/daily/${AWAITING_BRIEF_DATE}`);

  expect(response?.status()).toBe(404);
  await expect(page.getByText(AWAITING_SECRET)).toHaveCount(0);
});
