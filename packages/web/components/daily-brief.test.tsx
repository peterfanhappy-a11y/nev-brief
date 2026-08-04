import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DailyBrief, {
  estimateBriefReadMinutes,
  estimateChineseReadMinutes,
} from "@/components/daily-brief";
import type { AiPublishedBrief } from "@/lib/ai-briefs";

const COMPLETE_BRIEF: AiPublishedBrief = {
  briefDate: "2026-08-03",
  publishedAt: "2026-08-03T01:30:00.000Z",
  content: {
    version: 1,
    brief_date: "2026-08-03",
    subject: "智能体进入真实工作流",
    preheader: "另外：小模型效率继续提升",
    editorial: "今天的核心变化，是 AI 从回答问题走向完成工作。",
    intro_bullets: ["智能体开始进入团队流程", "推理成本继续下降"],
    today_ai: {
      theme: "model_research",
      header_image: "https://cdn.example.com/today.png",
      header_image_alt: "今日 AI 头图",
      subtitle: "今天最重要的 AI 动态",
      cta_label: "阅读原文",
      stories: [
        {
          headline: "模型获得更稳定的工具调用能力",
          summary: "新的训练方法显著降低了多步骤任务中的失败率。",
          url: "https://example.com/today",
          label: "模型更新",
        },
      ],
    },
    ai_masters: {
      theme: "product_tools",
      header_image: null,
      header_image_alt: "",
      subtitle: "从实践者身上学习",
      cta_label: "查看分享",
      stories: [
        {
          headline: "研究者分享智能体评测框架",
          summary: "框架将成功率、成本和延迟放在同一张评估表中。",
          url: "https://example.com/master",
          label: "实践分享",
        },
      ],
    },
    ai_research: {
      theme: "ai_research",
      header_image: null,
      header_image_alt: "",
      subtitle: "值得跟进的论文",
      cta_label: "阅读论文",
      stories: [
        {
          headline: "长上下文推理的新方法",
          summary: "论文提出分层检索机制，减少长文本任务中的注意力浪费。",
          url: "https://example.com/paper",
          label: "论文",
        },
      ],
    },
    ai_engineering: {
      theme: "ai_engineering",
      header_image: null,
      header_image_alt: "",
      subtitle: "本期工程要点",
      cta_label: "阅读原文",
      stories: [
        {
          headline: "为智能体增加可观测性",
          summary: "记录每次工具调用的输入、输出、成本和回退路径。",
          url: "",
          label: "工程实践",
        },
      ],
    },
    agent_tools: {
      theme: "agent_tools",
      header_image: null,
      header_image_alt: "",
      subtitle: "本周值得试用的项目",
      cta_label: "查看仓库",
      stories: [
        {
          headline: "开源任务编排工具",
          summary: "通过声明式配置组织多智能体任务和人工审批节点。",
          url: "https://example.com/agent-tool",
          label: "12k stars",
        },
      ],
    },
    featured: [
      {
        theme: "ethics_regulation",
        theme_label: "治理",
        headline: "企业发布 AI 治理指南",
        details: ["明确高风险场景", "要求保留人工复核"],
        significance: "指南为团队部署 AI 提供了可执行的风险边界。",
        url: "https://example.com/featured",
        source_name: "示例来源",
        og_image: "https://cdn.example.com/featured.png",
        article_id: "article-1",
      },
    ],
    tools: [
      {
        name: "工作流检查器",
        one_liner: "在发布前检查智能体工具权限",
        url: "https://example.com/tool",
      },
    ],
    daily_tip: {
      title: "先定义停止条件",
      body: "让智能体在信息不足时停止并请求人工确认。",
    },
    quick_hits: [
      { text: "新的开源评测集发布", url: "https://example.com/quick" },
      { text: "无链接快讯", url: undefined },
    ],
    yesterday_top: {
      headline: "昨日最受关注：本地模型部署",
      url: "https://example.com/yesterday",
    },
    model: "test-model",
    stage1_stats: { candidates: 24, dupe_groups: 3 },
  },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("estimateChineseReadMinutes", () => {
  it.each([
    ["", 1],
    ["字".repeat(400), 1],
    ["字".repeat(401), 2],
  ])("estimates %s characters deterministically", (text, expected) => {
    expect(estimateChineseReadMinutes(text)).toBe(expected);
  });

  it("counts representative digest and legacy prose across a minute boundary", () => {
    // Hand count: base 280 + digest 80 + legacy featured 41 = 401.
    const boundaryContent: AiPublishedBrief["content"] = {
      ...COMPLETE_BRIEF.content,
      subject: "主".repeat(40),
      editorial: "编".repeat(200),
      intro_bullets: ["引".repeat(40)],
      today_ai: {
        ...COMPLETE_BRIEF.content.today_ai!,
        subtitle: "",
        stories: [
          {
            headline: "研".repeat(40),
            summary: "摘".repeat(40),
            url: "",
            label: "",
          },
        ],
      },
      ai_masters: null,
      ai_research: null,
      ai_engineering: null,
      agent_tools: null,
      featured: [
        {
          ...COMPLETE_BRIEF.content.featured[0],
          theme_label: "",
          headline: "精".repeat(20),
          details: ["细".repeat(10)],
          significance: "义".repeat(10),
          source_name: "源",
          og_image: null,
        },
      ],
      tools: [],
      daily_tip: null,
      quick_hits: [],
      yesterday_top: null,
    };

    expect(estimateBriefReadMinutes(boundaryContent)).toBe(2);
    expect(
      estimateBriefReadMinutes({ ...boundaryContent, today_ai: null }),
    ).toBe(1);
    expect(
      estimateBriefReadMinutes({ ...boundaryContent, featured: [] }),
    ).toBe(1);
  });
});

describe("DailyBrief", () => {
  it("renders every current content module from the validated issue", () => {
    vi.stubGlobal("React", React);
    render(<DailyBrief brief={COMPLETE_BRIEF} />);

    expect(
      screen.getByRole("heading", { name: "智能体进入真实工作流" }),
    ).toBeInTheDocument();
    expect(screen.getByText(COMPLETE_BRIEF.content.editorial)).toBeInTheDocument();
    expect(screen.getByText("智能体开始进入团队流程")).toBeInTheDocument();

    for (const section of [
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
      expect(screen.getByRole("heading", { name: section })).toBeInTheDocument();
    }

    expect(screen.getByRole("img", { name: "今日 AI 头图" })).toHaveAttribute(
      "src",
      "https://cdn.example.com/today.png",
    );
    expect(
      screen.getByRole("img", { name: "企业发布 AI 治理指南 配图" }),
    ).toHaveAttribute("src", "https://cdn.example.com/featured.png");
    expect(screen.getByRole("link", { name: "阅读原文" })).toHaveAttribute(
      "href",
      "https://example.com/today",
    );
    expect(screen.getByRole("link", { name: "示例来源" })).toHaveAttribute(
      "href",
      "https://example.com/featured",
    );
    expect(
      screen.getByRole("link", { name: "新的开源评测集发布" }),
    ).toHaveAttribute("href", "https://example.com/quick");

    expect(screen.getByText("2026-08-03")).toHaveAttribute(
      "dateTime",
      "2026-08-03",
    );
    expect(screen.getByText(/\d+ 分钟阅读/)).toHaveTextContent("2 分钟阅读");
  });

  it("omits absent optional sections without losing the rest of the issue", () => {
    vi.stubGlobal("React", React);
    const brief: AiPublishedBrief = {
      ...COMPLETE_BRIEF,
      content: {
        ...COMPLETE_BRIEF.content,
        ai_masters: null,
        daily_tip: null,
      },
    };

    render(<DailyBrief brief={brief} />);

    expect(screen.queryByRole("heading", { name: "AI大神" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "每日技巧" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "AI研究" }),
    ).toBeInTheDocument();
  });

  it("keeps slot IDs and display-array keys unique without text invariants", () => {
    vi.stubGlobal("React", React);
    const repeatedStory = {
      headline: "重复新闻",
      summary: "重复摘要",
      url: "https://example.com/repeated-story",
      label: "重复标签",
    };
    const repeatedFeatured = {
      ...COMPLETE_BRIEF.content.featured[0],
      headline: "重复精选",
      details: ["重复细节", "重复细节"],
      url: "https://example.com/repeated-featured",
    };
    const repeatedTool = {
      name: "重复工具",
      one_liner: "重复说明",
      url: "https://example.com/repeated-tool",
    };
    const repeatedHit = {
      text: "重复快讯",
      url: "https://example.com/repeated-hit",
    };
    const brief: AiPublishedBrief = {
      ...COMPLETE_BRIEF,
      content: {
        ...COMPLETE_BRIEF.content,
        intro_bullets: ["重复重点", "重复重点"],
        today_ai: {
          ...COMPLETE_BRIEF.content.today_ai!,
          theme: "model_research",
          stories: [repeatedStory, { ...repeatedStory }],
        },
        ai_masters: {
          ...COMPLETE_BRIEF.content.ai_masters!,
          theme: "model_research",
          stories: [repeatedStory],
        },
        featured: [
          { ...repeatedFeatured, article_id: "article-duplicate-1" },
          { ...repeatedFeatured, article_id: "article-duplicate-2" },
        ],
        tools: [repeatedTool, { ...repeatedTool }],
        quick_hits: [repeatedHit, { ...repeatedHit }],
      },
    };
    const diagnostic = vi.spyOn(console, "error").mockImplementation(() => {});

    render(<DailyBrief brief={brief} />);

    const todayHeading = screen.getByRole("heading", { name: "今日AI" });
    const mastersHeading = screen.getByRole("heading", { name: "AI大神" });
    expect([todayHeading.id, mastersHeading.id]).toEqual([
      "daily-section-today-ai",
      "daily-section-ai-masters",
    ]);
    expect(todayHeading.closest("section")).toHaveAttribute(
      "aria-labelledby",
      "daily-section-today-ai",
    );
    expect(mastersHeading.closest("section")).toHaveAttribute(
      "aria-labelledby",
      "daily-section-ai-masters",
    );

    const diagnostics = diagnostic.mock.calls
      .flat()
      .map(String)
      .join("\n");
    expect(diagnostics).not.toContain("same key");
  });
});
