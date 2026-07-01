// 12 张手写中文 AI 新闻占位卡。首屏 6 卡，「加载更多」再展开后 6 卡。
// 后续换成真实 API 拉取时，替换 getMockPosts 的返回来源即可。

export type AIPost = {
  slug: string;         // 未来详情页路径 /p/[slug]，本轮不做
  title: string;
  summary: string;
  tag: "模型" | "工具" | "趋势" | "企业" | "监管" | "研究";
  date: string;         // YYYY-MM-DD
  cover: string;        // 封面色块（tailwind gradient class）
};

export const MOCK_AI_POSTS: AIPost[] = [
  {
    slug: "gpt-6-release",
    title: "OpenAI 发布 GPT-6：推理时长可控，Agent 模式默认开启",
    summary:
      "GPT-6 引入 thinking budget 参数，开发者可显式限制单次推理最长思考时间；同时 Agents API 从 preview 转为 GA，工具调用并发上限提高到 32。",
    tag: "模型",
    date: "2026-06-29",
    cover: "from-indigo-500 to-blue-500",
  },
  {
    slug: "claude-fable-5-china",
    title: "Anthropic Claude Fable 5 中文版评测：长文本能力接近母语水平",
    summary:
      "第三方 CLUE 基准显示，Claude Fable 5 在中文长文本理解、代码生成、数学推理上超过前代 20%，Anthropic 官方称其为「首个真正 bilingual 的旗舰」。",
    tag: "模型",
    date: "2026-06-28",
    cover: "from-orange-500 to-amber-500",
  },
  {
    slug: "deepseek-r2-open",
    title: "DeepSeek R2 开源：MoE 架构 + 671B 总参数，推理成本再降 40%",
    summary:
      "DeepSeek 在 GitHub 发布 R2 权重（MIT License），采用改进版 MoE + shared expert 设计，每 token 激活 37B 参数。第三方复现显示 API 成本可压到 GPT-6 的 1/8。",
    tag: "模型",
    date: "2026-06-27",
    cover: "from-emerald-500 to-teal-500",
  },
  {
    slug: "cursor-ide-agent",
    title: "Cursor 3.0 引入常驻 Agent：每晚自动 refactor，早上给你留 PR",
    summary:
      "新版 Cursor 支持后台常驻的 refactor agent，会在开发者下班后扫描代码库，把重复代码、命名不一致、type-any 修好，早上 review 一批 PR 即可。付费用户已开放。",
    tag: "工具",
    date: "2026-06-27",
    cover: "from-slate-700 to-slate-900",
  },
  {
    slug: "meta-llama-video-model",
    title: "Meta 发布 LLaVA-Video-70B：单模型统一视频理解、生成、编辑",
    summary:
      "Meta 开源了首个视频三合一模型 LLaVA-Video，可在同一模型里完成视频问答、文本生成视频（720p, 20s）、视频局部编辑。权重、训练数据、评估集全公开。",
    tag: "研究",
    date: "2026-06-26",
    cover: "from-pink-500 to-rose-500",
  },
  {
    slug: "china-ai-regulation-2026",
    title: "国家网信办发布《生成式 AI 服务管理办法（2026 修订）》",
    summary:
      "新版办法引入分级备案制：面向消费者的通用大模型（To C）走完整备案，垂直行业（企业内部）只需承诺制。开源模型免除备案义务但需在项目页显著标注训练数据来源。",
    tag: "监管",
    date: "2026-06-26",
    cover: "from-red-500 to-orange-500",
  },
  {
    slug: "byte-doubao-3",
    title: "字节豆包 3.0 上线：日活破 5000 万，广告与订阅双模式启动",
    summary:
      "豆包 App 更新至 3.0，除通用对话外集成豆包漫画、豆包写作、豆包播客三大生产力入口。字节公开表示 To C 端 2026 下半年测试订阅制 39 元/月 与免费带广告双模式。",
    tag: "企业",
    date: "2026-06-25",
    cover: "from-cyan-500 to-blue-600",
  },
  {
    slug: "ai-programming-jobs-2026",
    title: "斯坦福研究：AI 编程助手让初级工程师产出接近中级",
    summary:
      "对 2000 名开发者的 6 个月追踪显示，深度使用 Copilot / Cursor / Claude Code 的初级工程师，PR 合入率提高 68%，bug 引入率降低 22%，产出接近入职 3 年的中级水平。",
    tag: "研究",
    date: "2026-06-24",
    cover: "from-violet-500 to-purple-600",
  },
  {
    slug: "google-veo-3-realtime",
    title: "Google Veo 3 支持实时视频生成：延迟压到 200ms，直播场景可用",
    summary:
      "Veo 3 新增 realtime endpoint，输入文本 200ms 内出 512×512 视频流。Google Cloud 已上线 gaming NPC 对白直出 demo，虚拟主播赛道预计短期爆发。",
    tag: "工具",
    date: "2026-06-24",
    cover: "from-yellow-500 to-orange-500",
  },
  {
    slug: "ali-qwen-3-agentic",
    title: "阿里通义千问 Qwen3-Agentic 发布：原生 tool-use，128 工具并发调度",
    summary:
      "Qwen3-Agentic 在训练阶段引入 200 万条 agent trajectory，可原生调度 128 个并行工具调用。魔搭社区提供一键接入企业内部 MCP 服务器的适配层。",
    tag: "模型",
    date: "2026-06-23",
    cover: "from-blue-500 to-indigo-600",
  },
  {
    slug: "openai-mcp-marketplace",
    title: "OpenAI 上线 MCP Marketplace：3000+ 官方审核的工具与数据源",
    summary:
      "MCP 生态迎来集中入口，开发者可在 marketplace.openai.com 直接订阅工具（Notion、Linear、Figma、Salesforce 等），ChatGPT / GPT-6 API 双端一键启用。",
    tag: "趋势",
    date: "2026-06-22",
    cover: "from-teal-500 to-green-600",
  },
  {
    slug: "ai-startups-funding-q2",
    title: "2026 Q2 中国 AI 创业融资盘点：具身智能占 45%，Agent 平台占 22%",
    summary:
      "IT 桔子数据：Q2 中国 AI 领域披露融资 168 起、总额 380 亿元。具身智能（人形机器人 + 灵巧手）领跑，Agent 编排平台次之，行业垂类大模型融资继续萎缩。",
    tag: "趋势",
    date: "2026-06-22",
    cover: "from-fuchsia-500 to-pink-600",
  },
];

/** 前 n 条（首屏用 6，加载更多再来 6） */
export function getMockPosts(offset: number, limit: number): AIPost[] {
  return MOCK_AI_POSTS.slice(offset, offset + limit);
}

export const POSTS_PER_PAGE = 6;
