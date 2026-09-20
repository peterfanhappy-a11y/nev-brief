import { render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BrandIcon } from "@/components/brand-icon";

const OPTIMIZED_ASSETS = {
  bytedance: "/brand/companies/web/bytedance-v1.webp",
  alibaba: "/brand/companies/web/alibaba-v1.webp",
  tencent: "/brand/companies/web/tencent-v1.webp",
  deepseek: "/brand/companies/web/deepseek-v1.webp",
  xiaomi: "/brand/companies/web/xiaomi-v1.webp",
  huawei: "/brand/companies/web/huawei-v1.webp",
  weibo: "/brand/companies/web/weibo-v1.webp",
  wechat: "/brand/companies/web/wechat-v1.webp",
  douyin: "/brand/companies/web/douyin-v1.webp",
  xiaohongshu: "/brand/companies/web/xiaohongshu-v1.webp",
} as const;

describe("BrandIcon", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("serves each homepage brand from a versioned optimized asset", () => {
    render(
      <>
        {Object.entries(OPTIMIZED_ASSETS).map(([slug, src]) => (
          <BrandIcon key={slug} slug={slug} title={slug} />
        ))}
      </>,
    );

    for (const [slug, src] of Object.entries(OPTIMIZED_ASSETS)) {
      expect(screen.getByRole("img", { name: slug })).toHaveAttribute(
        "src",
        src,
      );
    }
  });
});
