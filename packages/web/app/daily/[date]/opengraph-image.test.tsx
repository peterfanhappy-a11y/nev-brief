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

  it("fits the maximum valid Unicode prose by code point and subsets exactly what it displays", async () => {
    const maxSubject = "题".repeat(30) + "🚀" + "尾".repeat(12);
    const maxEditorial = "编".repeat(94) + "🧠" + "尾".repeat(124);
    const displayedSubject = "题".repeat(30) + "🚀…";
    const displayedEditorial = "编".repeat(94) + "🧠…";
    expect(maxSubject).toHaveLength(44);
    expect(maxEditorial).toHaveLength(220);
    mocks.getPublishedBrief.mockResolvedValueOnce({
      ...PUBLISHED_BRIEF,
      content: {
        ...PUBLISHED_BRIEF.content,
        subject: maxSubject,
        editorial: maxEditorial,
      },
    });

    await OGImage({ params: params("2026-08-03") });

    const [element] = mocks.imageResponse.mock.calls[0] as [React.ReactElement];
    render(element);
    expect(screen.getByText(displayedSubject)).toBeInTheDocument();
    expect(screen.getByText(displayedEditorial)).toBeInTheDocument();
    expect(screen.queryByText(maxSubject)).not.toBeInTheDocument();
    expect(screen.queryByText(maxEditorial)).not.toBeInTheDocument();
    expect(Array.from(displayedSubject)).toHaveLength(32);
    expect(Array.from(displayedEditorial)).toHaveLength(96);
    expect(`${displayedSubject}${displayedEditorial}`).not.toContain("�");

    const displayedText =
      `AIVIZENS2026-08-03${displayedSubject}${displayedEditorial}`;
    expect(mocks.loadCjkFont).toHaveBeenNthCalledWith(1, 400, displayedText);
    expect(mocks.loadCjkFont).toHaveBeenNthCalledWith(2, 700, displayedText);
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

  it("returns a safe ASCII fallback on font failure and retries full rendering later", async () => {
    const diagnostic = vi.spyOn(console, "error").mockImplementation(() => {});
    mocks.loadCjkFont.mockReset();
    mocks.loadCjkFont
      .mockRejectedValueOnce(
        new Error("font request exposed secret-font-token"),
      )
      .mockRejectedValueOnce(
        new Error("font request exposed secret-font-token"),
      )
      .mockResolvedValueOnce(new ArrayBuffer(4))
      .mockResolvedValueOnce(new ArrayBuffer(8));

    await OGImage({ params: params("2026-08-03") });

    const [fallbackElement, fallbackOptions] = mocks.imageResponse.mock
      .calls[0] as [React.ReactElement, Record<string, unknown>];
    render(fallbackElement);
    expect(screen.getByText("AIVIZENS")).toBeInTheDocument();
    expect(screen.getByText("2026-08-03")).toBeInTheDocument();
    expect(screen.queryByText("真实日报标题")).not.toBeInTheDocument();
    expect(
      screen.queryByText("只呈现经过发布边界验证的编辑寄语。"),
    ).not.toBeInTheDocument();
    expect(document.body.textContent).toMatch(/^[\x00-\x7F]*$/);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(JSON.stringify(fallbackElement)).not.toContain(
      "https://cdn.example.com/should-not-load.png",
    );
    expect(fallbackOptions).toEqual({ width: 1200, height: 630 });
    expect(diagnostic.mock.calls).toEqual([
      ["[daily-og] CJK font unavailable"],
    ]);
    expect(diagnostic.mock.calls.flat().join("\n")).not.toContain(
      "secret-font-token",
    );

    cleanup();
    await OGImage({ params: params("2026-08-03") });

    const [fullElement, fullOptions] = mocks.imageResponse.mock.calls[1] as [
      React.ReactElement,
      { fonts?: unknown[] },
    ];
    render(fullElement);
    expect(screen.getByText("真实日报标题")).toBeInTheDocument();
    expect(
      screen.getByText("只呈现经过发布边界验证的编辑寄语。"),
    ).toBeInTheDocument();
    expect(fullOptions.fonts).toHaveLength(2);
    expect(mocks.loadCjkFont).toHaveBeenCalledTimes(4);
  });
});
