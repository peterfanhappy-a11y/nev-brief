import type { AiBriefContent } from "@/lib/ai-briefs";

interface DisposableFixtureEnvironment {
  AIVIZENS_DISPOSABLE_STACK?: string;
  SUPABASE_URL?: string;
}

export function assertDisposableFixtureTarget(
  environment: DisposableFixtureEnvironment,
): void {
  if (environment.AIVIZENS_DISPOSABLE_STACK !== "true") {
    throw new Error(
      "Fixture mutation requires AIVIZENS_DISPOSABLE_STACK=true",
    );
  }

  let target: URL;
  try {
    target = new URL(environment.SUPABASE_URL ?? "");
  } catch {
    throw new Error("Fixture mutation requires an http loopback SUPABASE_URL");
  }

  const loopbackHosts = new Set(["127.0.0.1", "localhost", "[::1]"]);
  if (target.protocol !== "http:" || !loopbackHosts.has(target.hostname)) {
    throw new Error("Fixture mutation requires an http loopback SUPABASE_URL");
  }
}

export const PUBLISHED_BRIEF_DATE = "2026-08-01";
export const AWAITING_BRIEF_DATE = "2026-08-02";
export const AWAITING_SECRET = "AWAITING_ONLY_SECRET_7F3C91";

function digestSection(
  theme:
    | "model_research"
    | "product_tools"
    | "ai_research"
    | "ai_engineering"
    | "agent_tools",
  headline: string,
  summary: string,
) {
  return {
    theme,
    header_image: null,
    header_image_alt: "",
    subtitle: `${headline}栏目摘要`,
    cta_label: "阅读原文",
    stories: [
      {
        headline,
        summary,
        url: `https://example.com/${theme}`,
        label: "Fixture Source",
      },
    ],
  };
}

export const PUBLISHED_BRIEF_CONTENT: AiBriefContent = {
  version: 1,
  brief_date: PUBLISHED_BRIEF_DATE,
  subject: "Fixture 已发布 AI 日报",
  preheader: "完整公开日报的浏览器验收描述",
  editorial: "这份日报只来自 disposable Postgres 中的已发布测试数据。",
  intro_bullets: ["五个 Digest 栏目全部可见", "兼容内容模块全部可见"],
  today_ai: digestSection(
    "model_research",
    "今日AI Fixture 新闻",
    "今日AI模块的公开摘要。",
  ),
  ai_masters: digestSection(
    "product_tools",
    "AI大神 Fixture 新闻",
    "AI大神模块的公开摘要。",
  ),
  ai_research: digestSection(
    "ai_research",
    "AI研究 Fixture 新闻",
    "AI研究模块的公开摘要。",
  ),
  ai_engineering: digestSection(
    "ai_engineering",
    "AI工程 Fixture 新闻",
    "AI工程模块的公开摘要。",
  ),
  agent_tools: digestSection(
    "agent_tools",
    "Agent工具 Fixture 新闻",
    "Agent工具模块的公开摘要。",
  ),
  featured: [
    {
      theme: "skills_efficiency",
      theme_label: "效率技能",
      headline: "Legacy 精选 Fixture",
      details: ["Legacy 精选细节"],
      significance: "验证兼容精选模块仍然公开渲染。",
      url: "https://example.com/featured",
      source_name: "Fixture Source",
      og_image: null,
      article_id: "fixture-article-1",
    },
  ],
  tools: [
    {
      name: "Fixture AI Tool",
      one_liner: "验证兼容工具模块。",
      url: "https://example.com/tool",
    },
  ],
  daily_tip: {
    title: "Fixture 每日技巧",
    body: "先验证来源，再把结论加入工作流。",
  },
  quick_hits: [
    {
      text: "Fixture 快讯",
      url: "https://example.com/quick-hit",
    },
  ],
  yesterday_top: {
    headline: "Fixture 昨日热门",
    url: "https://example.com/yesterday",
  },
  opc_case: null,
  model: "fixture-model",
  stage1_stats: { candidates: 12, dupe_groups: 2 },
};

// Rendering/schema fixture only: inherited story counts are not production quality-valid.
export const PUBLISHED_BRIEF_V3_RENDERING_CONTENT: AiBriefContent = {
  ...PUBLISHED_BRIEF_CONTENT,
  version: 3,
  intro_bullets: [
    "OPC 案例：从失败中重建电商 AI 产品",
    "今日 AI：智能体走入实际工作流",
    "AI 大神：分享可复用的实践经验",
    "工具学习：论文方法与 Agent 工具",
  ],
  opc_case: {
    sharer: "Ruslan",
    headline: "$8M 产品一夜归零，Zipchat 再冲到 $2M ARR",
    summary: "他重建电商 AI 销售代理，通过客户反馈持续改进产品并恢复增长。",
    original_revenue: "$167K MRR",
    monthly_revenue_usd: 167_000,
    revenue_display: "$167K 美元月度营收",
    url: "https://www.indiehackers.com/post/example",
    header_image: "https://cdn.example.com/opc.png",
    header_image_alt: "Ruslan 的 Zipchat 案例",
  },
  ai_engineering: null,
  featured: [],
  tools: [],
  daily_tip: null,
  quick_hits: [],
  yesterday_top: null,
};

export interface AiDailyBriefFixtureRow {
  brief_date: string;
  content: AiBriefContent;
  model: string;
  status: "published" | "awaiting_approval";
  quality_report: Record<string, unknown>;
  approved_at: string | null;
  published_at: string | null;
}

export const PUBLISHED_BRIEF_ROW: AiDailyBriefFixtureRow = {
  brief_date: PUBLISHED_BRIEF_DATE,
  content: PUBLISHED_BRIEF_CONTENT,
  model: "fixture-model",
  status: "published",
  quality_report: { passed: true, blockers: [], warnings: [], metrics: {} },
  approved_at: "2026-08-01T00:30:00.000Z",
  published_at: "2026-08-01T01:00:00.000Z",
};

export const AWAITING_BRIEF_ROW: AiDailyBriefFixtureRow = {
  ...PUBLISHED_BRIEF_ROW,
  brief_date: AWAITING_BRIEF_DATE,
  content: {
    ...PUBLISHED_BRIEF_CONTENT,
    brief_date: AWAITING_BRIEF_DATE,
    subject: AWAITING_SECRET,
    preheader: "未发布内容不得出现在任何公开页面",
    editorial: `未发布的唯一标记：${AWAITING_SECRET}`,
  },
  status: "awaiting_approval",
  approved_at: null,
  published_at: null,
};

export const DAILY_ARCHIVE_FIXTURE_ROWS = [
  PUBLISHED_BRIEF_ROW,
  AWAITING_BRIEF_ROW,
];
