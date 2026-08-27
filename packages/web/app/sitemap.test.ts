import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  listPublishedBriefDates: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("@/lib/ai-briefs", () => ({
  listPublishedBriefDates: mocks.listPublishedBriefDates,
}));

import { metadata } from "@/app/layout";
import robots from "@/app/robots";
import sitemap from "@/app/sitemap";

describe("AIVIZENS public discovery metadata", () => {
  beforeEach(() => {
    vi.stubEnv("WEB_BASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_WEB_BASE_URL", "");
    mocks.listPublishedBriefDates.mockResolvedValue([
      {
        briefDate: "2026-08-03",
        publishedAt: "2026-08-03T01:30:00.000Z",
      },
      {
        briefDate: "2026-08-02",
        publishedAt: "2026-08-02T01:30:00.000Z",
      },
    ]);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  it("maps the homepage and published archive dates to canonical URLs newest-first", async () => {
    const entries = await sitemap();

    expect(entries).toEqual([
      {
        url: "https://aivizens.com",
        changeFrequency: "weekly",
        priority: 1,
      },
      {
        url: "https://aivizens.com/daily/2026-08-03",
        lastModified: new Date("2026-08-03T01:30:00.000Z"),
        changeFrequency: "daily",
        priority: 0.8,
      },
      {
        url: "https://aivizens.com/daily/2026-08-02",
        lastModified: new Date("2026-08-02T01:30:00.000Z"),
        changeFrequency: "daily",
        priority: 0.8,
      },
    ]);
    expect(entries.map((entry) => entry.url).join("\n")).not.toContain(
      "/nev",
    );
  });

  it("keeps a discovery outage operational instead of publishing a root-only sitemap", async () => {
    mocks.listPublishedBriefDates.mockRejectedValueOnce(
      new Error("Published brief dates unavailable"),
    );

    await expect(sitemap()).rejects.toThrow(
      "Published brief dates unavailable",
    );
  });

  it("allows public archives while excluding operational and non-public paths", () => {
    expect(robots()).toEqual({
      rules: [
        {
          userAgent: "*",
          allow: ["/", "/daily/"],
          disallow: [
            "/confirm",
            "/unsubscribe",
            "/rate",
            "/api",
            "/preview",
            "/manage",
            "/subscribed",
          ],
        },
      ],
      sitemap: "https://aivizens.com/sitemap.xml",
      host: "https://aivizens.com",
    });
  });

  it("defines AIVIZENS root metadata on the production canonical base", () => {
    expect(metadata.metadataBase?.toString()).toBe("https://aivizens.com/");
    expect(metadata).toMatchObject({
      title: "AIVIZENS · 每日 AI 精选",
      description: "每日 5 分钟，学会 AI。最新 AI 资讯、行业趋势与实用工具。",
      alternates: { canonical: "/" },
      openGraph: {
        type: "website",
        url: "/",
        siteName: "AIVIZENS",
        title: "AIVIZENS · 每日 AI 精选",
      },
    });
    expect(JSON.stringify(metadata)).not.toContain("NEV");
  });
});
