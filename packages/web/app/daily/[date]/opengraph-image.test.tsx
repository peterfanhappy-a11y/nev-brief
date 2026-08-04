import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AiPublishedBrief } from "@/lib/ai-briefs";

const mocks = vi.hoisted(() => ({
  getPublishedBrief: vi.fn(),
  imageResponse: vi.fn(),
  loadCjkFont: vi.fn(),
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
  };
});
vi.mock("@/lib/og-font", () => ({
  loadCjkFont: mocks.loadCjkFont,
}));
vi.mock("next/navigation", () => ({
  notFound: mocks.notFound,
}));
vi.mock("next/og", () => ({
  ImageResponse: class FakeImageResponse {
    constructor(element: React.ReactElement, options: Record<string, unknown>) {
      mocks.imageResponse(element, options);
    }
  },
}));

import OGImage, {
  alt,
  contentType,
  size,
} from "@/app/daily/[date]/opengraph-image";

const PUBLISHED_BRIEF: AiPublishedBrief = {
  briefDate: "2026-08-03",
  publishedAt: "2026-08-03T01:30:00.000Z",
  content: {
    version: 1,
    brief_date: "2026-08-03",
    subject: "真实日报标题",
    preheader: "不应渲染的预览文字",
    editorial: "只呈现经过发布边界验证的编辑寄语。",
    intro_bullets: ["不应渲染的重点"],
    today_ai: {
      theme: "model_research",
      header_image: "https://cdn.example.com/should-not-load.png",
      header_image_alt: "不应渲染的远程图片",
      subtitle: "不应渲染的栏目副标题",
      cta_label: "阅读原文",
      stories: [
        {
          headline: "不应渲染的栏目新闻",
          summary: "不应渲染的栏目摘要",
          url: "https://example.com/story",
          label: "来源",
        },
      ],
    },
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

describe("daily archive OpenGraph image", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    mocks.getPublishedBrief.mockResolvedValue(PUBLISHED_BRIEF);
    mocks.loadCjkFont
      .mockResolvedValueOnce(new ArrayBuffer(4))
      .mockResolvedValueOnce(new ArrayBuffer(8));
    mocks.notFound.mockImplementation(() => {
      throw new Error("NEXT_NOT_FOUND");
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.resetAllMocks();
  });

  it("renders only published AIVIZENS issue prose with bundled CJK font data", async () => {
    await OGImage({ params: params("2026-08-03") });

    const [element, options] = mocks.imageResponse.mock.calls[0] as [
      React.ReactElement,
      {
        width: number;
        height: number;
        fonts: Array<{ name: string; data: ArrayBuffer; weight: number }>;
      },
    ];
    render(element);

    expect(screen.getByText("AIVIZENS")).toBeInTheDocument();
    expect(screen.getByText("2026-08-03")).toBeInTheDocument();
    expect(screen.getByText("真实日报标题")).toBeInTheDocument();
    expect(
      screen.getByText("只呈现经过发布边界验证的编辑寄语。"),
    ).toBeInTheDocument();
    expect(screen.queryByText("不应渲染的预览文字")).not.toBeInTheDocument();
    expect(screen.queryByText("不应渲染的重点")).not.toBeInTheDocument();
    expect(screen.queryByText("不应渲染的栏目新闻")).not.toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(JSON.stringify(element)).not.toContain(
      "https://cdn.example.com/should-not-load.png",
    );
    expect(options).toMatchObject({ width: 1200, height: 630 });
    expect(options.fonts).toEqual([
      {
        name: "Noto Sans SC",
        data: expect.any(ArrayBuffer),
        style: "normal",
        weight: 400,
      },
      {
        name: "Noto Sans SC",
        data: expect.any(ArrayBuffer),
        style: "normal",
        weight: 700,
      },
    ]);
    expect({ alt, contentType, size }).toEqual({
      alt: "AIVIZENS AI 日报",
      contentType: "image/png",
      size: { width: 1200, height: 630 },
    });
  });

  it.each(["2026-8-03", "2026-02-29"])(
    "rejects invalid archive date %s before reading content",
    async (date) => {
      await expect(OGImage({ params: params(date) })).rejects.toThrow(
        "NEXT_NOT_FOUND",
      );
      expect(mocks.getPublishedBrief).not.toHaveBeenCalled();
      expect(mocks.imageResponse).not.toHaveBeenCalled();
    },
  );

  it("rejects an unpublished archive date instead of returning an image", async () => {
    mocks.getPublishedBrief.mockResolvedValueOnce(null);

    await expect(
      OGImage({ params: params("2026-08-03") }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
    expect(mocks.imageResponse).not.toHaveBeenCalled();
  });

  it("propagates a safe published-query outage instead of treating it as unpublished", async () => {
    mocks.getPublishedBrief.mockRejectedValueOnce(
      new Error("Published brief unavailable"),
    );

    await expect(
      OGImage({ params: params("2026-08-03") }),
    ).rejects.toThrow("Published brief unavailable");
    expect(mocks.notFound).not.toHaveBeenCalled();
    expect(mocks.imageResponse).not.toHaveBeenCalled();
  });
});
