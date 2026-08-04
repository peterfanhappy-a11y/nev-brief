import React from "react";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LatestBriefsGrid from "@/components/latest-briefs-grid";
import type { AiBriefSummary } from "@/lib/ai-briefs";

const BRIEFS: AiBriefSummary[] = [
  {
    briefDate: "2026-08-03",
    subject: "智能体开始接管重复工作",
    preheader: "另外：推理模型迎来更新",
    editorial: "今天值得关注的是智能体从演示走向真实团队协作。",
    modules: ["今日AI", "Agent工具"],
    publishedAt: "2026-08-03T01:00:00.000Z",
  },
  {
    briefDate: "2026-08-02",
    subject: "小模型的效率突破",
    preheader: "另外：新的开源数据集",
    editorial: "更小的参数规模正在带来更实用的本地部署选择。",
    modules: ["AI研究"],
    publishedAt: "2026-08-02T01:00:00.000Z",
  },
  {
    briefDate: "2026-08-01",
    subject: "AI 工程进入稳定交付阶段",
    preheader: "另外：评测方法更新",
    editorial: "团队开始把注意力从原型速度转向可靠性与可观测性。",
    modules: ["AI工程"],
    publishedAt: "2026-08-01T01:00:00.000Z",
  },
  {
    briefDate: "2026-07-31",
    subject: "多模态搜索的新进展",
    preheader: "另外：视频理解工具",
    editorial: "图片、语音和文本检索正在汇入统一的产品体验。",
    modules: ["AI大神"],
    publishedAt: "2026-07-31T01:00:00.000Z",
  },
  {
    briefDate: "2026-07-30",
    subject: "企业开始重做知识工作流",
    preheader: "另外：权限治理实践",
    editorial: "真正的价值来自把模型能力嵌入已有流程，而不是增加聊天窗口。",
    modules: ["今日AI"],
    publishedAt: "2026-07-30T01:00:00.000Z",
  },
  {
    briefDate: "2026-07-29",
    subject: "开源模型生态继续扩张",
    preheader: "另外：推理成本下降",
    editorial: "更多可组合组件让团队拥有了新的技术路线选择。",
    modules: ["AI研究", "AI工程"],
    publishedAt: "2026-07-29T01:00:00.000Z",
  },
  {
    briefDate: "2026-07-28",
    subject: "不应渲染的第七期",
    preheader: "列表上限之外",
    editorial: "这个卡片必须被六期上限截断。",
    modules: ["Agent工具"],
    publishedAt: "2026-07-28T01:00:00.000Z",
  },
];

describe("LatestBriefsGrid", () => {
  it("renders at most six real daily issues with semantic archive links", () => {
    const { container } = render(<LatestBriefsGrid briefs={BRIEFS} />);

    expect(
      screen.getByRole("heading", { name: "最新日报" }),
    ).toBeInTheDocument();
    expect(container.querySelectorAll("article")).toHaveLength(6);
    expect(container.querySelectorAll("time")).toHaveLength(6);

    const newestCard = screen
      .getByRole("heading", { name: "智能体开始接管重复工作" })
      .closest("article");
    expect(newestCard).not.toBeNull();
    expect(within(newestCard!).getByText("2026-08-03")).toHaveAttribute(
      "dateTime",
      "2026-08-03",
    );
    expect(
      within(newestCard!).getByText(
        "今天值得关注的是智能体从演示走向真实团队协作。",
      ),
    ).toBeInTheDocument();
    expect(within(newestCard!).getByText("今日AI")).toBeInTheDocument();
    expect(within(newestCard!).getByText("Agent工具")).toBeInTheDocument();
    expect(
      within(newestCard!).getByRole("link", { name: /智能体开始接管重复工作/ }),
    ).toHaveAttribute("href", "/daily/2026-08-03");

    expect(screen.getByText("开源模型生态继续扩张")).toBeInTheDocument();
    expect(screen.queryByText("不应渲染的第七期")).not.toBeInTheDocument();
    expect(screen.queryByText("阅读全文")).not.toBeInTheDocument();
  });

  it("keeps a subscription path visible while the first issue is prepared", () => {
    render(<LatestBriefsGrid briefs={[]} />);

    expect(screen.getByText(/第一期日报正在准备中/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /订阅/ })).toHaveAttribute(
      "href",
      "#subscribe",
    );
  });
});
