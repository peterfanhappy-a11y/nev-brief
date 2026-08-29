import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AiPublishedBrief } from "@/lib/ai-briefs";

const mocks = vi.hoisted(() => ({
  getPublishedBrief: vi.fn(),
  getPublishedNeighbors: vi.fn(),
  notFound: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("@/lib/supabase", () => ({ getSupabaseAdmin: vi.fn() }));
vi.mock("@/lib/ai-briefs", async () => {
  const actual = await vi.importActual<typeof import("@/lib/ai-briefs")>(
    "@/lib/ai-briefs",
  );
  return {
    ...actual,
    getPublishedBrief: mocks.getPublishedBrief,
    getPublishedNeighbors: mocks.getPublishedNeighbors,
  };
});

vi.mock("next/navigation", () => ({
  notFound: mocks.notFound,
}));

import DailyArchivePage, { generateMetadata } from "@/app/daily/[date]/page";

const PUBLISHED_BRIEF: AiPublishedBrief = {
  briefDate: "2026-08-03",
  publishedAt: "2026-08-03T01:30:00.000Z",
  content: {
    version: 1,
    brief_date: "2026-08-03",
    subject: "真实日报标题",
    preheader: "另外：今日还有两项更新",
    editorial: "这是一份只读的已发布日报。",
    intro_bullets: ["第一项重点"],
    today_ai: null,
    ai_masters: null,
    ai_research: null,
    ai_engineering: null,
    agent_tools: null,
    featured: [],
    tools: [],
    daily_tip: null,
    quick_hits: [],
    yesterday_top: null,
    model: null,
    stage1_stats: null,
  },
};

const params = (date: string) => Promise.resolve({ date });

describe("daily archive page", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    vi.stubEnv("WEB_BASE_URL", "https://preview.aivizens.invalid/");
    mocks.getPublishedBrief.mockResolvedValue(PUBLISHED_BRIEF);
    mocks.getPublishedNeighbors.mockResolvedValue({
      previous: "2026-08-02",
      next: "2026-08-04",
    });
    mocks.notFound.mockImplementation(() => {
      throw new Error("NEXT_NOT_FOUND");
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders a published issue with closest navigation and subscription CTA", async () => {
    render(await DailyArchivePage({ params: params("2026-08-03") }));

    expect(
      screen.getByRole("heading", { name: "真实日报标题" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /上一期.*2026-08-02/ })).toHaveAttribute(
      "href",
      "/daily/2026-08-02",
    );
    expect(screen.getByRole("link", { name: /下一期.*2026-08-04/ })).toHaveAttribute(
      "href",
      "/daily/2026-08-04",
    );
    expect(screen.getByRole("link", { name: /免费订阅 AIVIZENS/ })).toHaveAttribute(
      "href",
      "/#subscribe",
    );
  });

  it.each(["2026-8-03", "2026-02-29"])(
    "calls notFound for invalid canonical date %s",
    async (date) => {
      await expect(DailyArchivePage({ params: params(date) })).rejects.toThrow(
        "NEXT_NOT_FOUND",
      );
      expect(mocks.getPublishedBrief).not.toHaveBeenCalled();
    },
  );

  it("calls notFound for a valid date with no published issue", async () => {
    mocks.getPublishedBrief.mockResolvedValueOnce(null);

    await expect(
      DailyArchivePage({ params: params("2026-08-03") }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
    expect(mocks.getPublishedNeighbors).not.toHaveBeenCalled();
  });

  it("propagates a safe operational failure instead of returning 404", async () => {
    mocks.getPublishedBrief.mockRejectedValueOnce(
      new Error("Published brief unavailable"),
    );

    const request = DailyArchivePage({ params: params("2026-08-03") });

    await expect(request).rejects.toThrow("Published brief unavailable");
    await expect(request).rejects.not.toThrow("NEXT_NOT_FOUND");
    expect(mocks.notFound).not.toHaveBeenCalled();
  });

  it("propagates a safe neighbor outage instead of silently dropping navigation", async () => {
    mocks.getPublishedNeighbors.mockRejectedValueOnce(
      new Error("Published brief neighbors unavailable"),
    );

    await expect(
      DailyArchivePage({ params: params("2026-08-03") }),
    ).rejects.toThrow("Published brief neighbors unavailable");
    expect(mocks.notFound).not.toHaveBeenCalled();
  });
});

describe("daily archive metadata", () => {
  beforeEach(() => {
    vi.stubEnv("WEB_BASE_URL", "https://preview.aivizens.invalid/");
    mocks.getPublishedBrief.mockResolvedValue(PUBLISHED_BRIEF);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  it("publishes canonical and OpenGraph data only for the published issue", async () => {
    const metadata = await generateMetadata({ params: params("2026-08-03") });

    expect(metadata).toMatchObject({
      title: "真实日报标题 · AIVIZENS 日报",
      description: "另外：今日还有两项更新",
      alternates: {
        canonical: "https://preview.aivizens.invalid/daily/2026-08-03",
      },
      robots: { index: true, follow: true },
      openGraph: {
        type: "article",
        url: "https://preview.aivizens.invalid/daily/2026-08-03",
        siteName: "AIVIZENS",
        title: "真实日报标题 · AIVIZENS 日报",
        description: "另外：今日还有两项更新",
        publishedTime: "2026-08-03T01:30:00.000Z",
        images: [
          {
            url: "https://preview.aivizens.invalid/daily/2026-08-03/opengraph-image",
            width: 1200,
            height: 630,
            alt: "真实日报标题 · AIVIZENS 日报",
          },
        ],
      },
    });
  });

  it.each(["not-a-date", "2026-08-03"])(
    "omits public metadata for non-public date %s",
    async (date) => {
      if (date === "2026-08-03") {
        mocks.getPublishedBrief.mockResolvedValueOnce(null);
      }

      const metadata = await generateMetadata({ params: params(date) });

      expect(metadata).toEqual({
        title: "AIVIZENS 日报",
        robots: { index: false, follow: false },
      });
    },
  );

  it("keeps metadata query outages operational", async () => {
    mocks.getPublishedBrief.mockRejectedValueOnce(
      new Error("Published brief unavailable"),
    );

    await expect(
      generateMetadata({ params: params("2026-08-03") }),
    ).rejects.toThrow("Published brief unavailable");
  });
});
