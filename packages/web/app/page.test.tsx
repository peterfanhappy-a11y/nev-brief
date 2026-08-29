import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AiBriefSummary } from "@/lib/ai-briefs";

const mocks = vi.hoisted(() => ({
  listPublishedBriefs: vi.fn(),
}));

vi.mock("@/lib/ai-briefs", () => ({
  listPublishedBriefs: mocks.listPublishedBriefs,
}));

import AiTrendsHome from "@/app/page";

const PUBLISHED_BRIEF: AiBriefSummary = {
  briefDate: "2026-08-03",
  subject: "真实发布日报",
  preheader: "今天的第二条动态",
  editorial: "这是从已发布简报读取的编辑导语。",
  modules: ["今日AI", "AI研究"],
  publishedAt: "2026-08-03T01:00:00.000Z",
};

async function renderHomepage() {
  render(await AiTrendsHome());
}

describe("AIVIZENS homepage", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    vi.stubEnv("SUBSCRIPTIONS_ENABLED", "false");
    mocks.listPublishedBriefs.mockResolvedValue([PUBLISHED_BRIEF]);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("loads the latest six published summaries into the daily grid", async () => {
    await renderHomepage();

    expect(mocks.listPublishedBriefs).toHaveBeenCalledWith(6);
    expect(
      screen.getByRole("heading", { name: "真实发布日报" }),
    ).toBeInTheDocument();
    const briefCard = screen.getByRole("heading", { name: "真实发布日报" }).closest("article");
    expect(briefCard?.querySelector('a[href="/daily/2026-08-03"]')).not.toBeNull();
  });

  it("preserves the approved subscription, trust, logo, and social shell", async () => {
    await renderHomepage();

    expect(
      screen.getByRole("heading", { name: /每日 5 分钟.*学会 AI/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "订阅" })).toHaveAttribute(
      "href",
      "/#subscribe",
    );
    expect(screen.getByRole("link", { name: "退订" })).toHaveAttribute(
      "href",
      "/unsubscribe",
    );
    expect(screen.getByText("订阅暂未开放")).toBeInTheDocument();
    expect(screen.getByText("100,000+")).toBeInTheDocument();

    for (const company of [
      "字节跳动",
      "阿里巴巴",
      "腾讯",
      "DeepSeek",
      "小米",
      "华为",
    ]) {
      expect(screen.getByRole("img", { name: company })).toBeInTheDocument();
    }
    const bytedanceLogo = screen.getByRole("img", { name: "字节跳动" });
    expect(bytedanceLogo.parentElement?.parentElement).not.toHaveClass("grayscale");

    for (const social of ["微博", "微信", "抖音", "小红书"]) {
      expect(screen.getByRole("link", { name: social })).toHaveAttribute(
        "href",
        "#",
      );
    }
    expect(
      screen.getByText(/加入 10 万\+ 专业人士/),
    ).toBeInTheDocument();
  });

  it("fails closed with a distinct unavailable state and a safe diagnostic", async () => {
    mocks.listPublishedBriefs.mockRejectedValueOnce(
      new Error("database failed with secret-token-123"),
    );
    const diagnostic = vi.spyOn(console, "error").mockImplementation(() => {});

    await renderHomepage();

    expect(
      screen.getByRole("heading", { name: "日报暂时无法加载" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/第一期日报正在准备中/)).not.toBeInTheDocument();
    expect(screen.queryByText(/secret-token-123/)).not.toBeInTheDocument();
    expect(diagnostic).toHaveBeenCalledTimes(1);
    expect(diagnostic).toHaveBeenCalledWith(
      "[homepage] published briefs unavailable",
    );
    expect(JSON.stringify(diagnostic.mock.calls)).not.toContain(
      "secret-token-123",
    );
  });
});
