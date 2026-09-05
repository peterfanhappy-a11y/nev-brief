import "server-only";

import { z } from "zod";

import { getSupabaseAdmin } from "@/lib/supabase";

const MAX_PUBLISHED_BRIEFS = 6;
const PUBLISHED_DATE_PAGE_SIZE = 1000;
const BRIEF_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function isHttpsUrl(value: string): boolean {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

export function isBriefDate(value: string): boolean {
  if (!BRIEF_DATE_RE.test(value)) return false;

  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));

  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

const BriefDateSchema = z.string().refine(isBriefDate, "Invalid brief date");
const HttpsUrlSchema = z
  .string()
  .refine(isHttpsUrl, "Required source URLs must use HTTPS");
const OptionalImageUrlSchema = z
  .string()
  .nullish()
  .transform((value) => (value && isHttpsUrl(value) ? value : null));
const OptionalSourceUrlSchema = z
  .string()
  .nullish()
  .transform((value) => (value && isHttpsUrl(value) ? value : undefined));
const OptionalDigestUrlSchema = z
  .string()
  .default("")
  .transform((value) => (value && isHttpsUrl(value) ? value : ""));

const ThemeSchema = z.enum([
  "model_research",
  "product_tools",
  "skills_efficiency",
  "ethics_regulation",
  "ai_research",
  "ai_engineering",
  "agent_tools",
]);

const FeaturedItemSchema = z.object({
  theme: ThemeSchema,
  theme_label: z.string(),
  headline: z.string().max(40),
  details: z.array(z.string()).min(1).max(5),
  significance: z.string().max(160),
  url: HttpsUrlSchema,
  source_name: z.string(),
  og_image: OptionalImageUrlSchema,
  article_id: z.string().nullish().transform((value) => value ?? null),
});

const DigestStorySchema = z.object({
  headline: z.string().max(80),
  summary: z.string().max(260),
  url: OptionalDigestUrlSchema,
  label: z.string().default(""),
});

const DigestSectionSchema = z.object({
  theme: ThemeSchema,
  header_image: OptionalImageUrlSchema,
  header_image_alt: z.string().default(""),
  subtitle: z.string().default(""),
  cta_label: z.string().default("阅读原文"),
  stories: z.array(DigestStorySchema).min(1).max(6),
});

const OptionalDigestSectionSchema = DigestSectionSchema.nullish().transform(
  (value) => value ?? null,
);

const ToolSchema = z.object({
  name: z.string().max(40),
  one_liner: z.string().max(60),
  url: HttpsUrlSchema,
});

const DailyTipSchema = z.object({
  title: z.string().max(30),
  body: z.string().max(260),
});

const QuickHitSchema = z.object({
  text: z.string().max(80),
  url: OptionalSourceUrlSchema,
});

const YesterdayTopSchema = z.object({
  headline: z.string(),
  url: HttpsUrlSchema,
});

const Stage1StatsSchema = z.object({
  candidates: z.number().int().default(0),
  dupe_groups: z.number().int().default(0),
});

export const AiBriefContentSchema = z.object({
  version: z.union([z.literal(1), z.literal(2)]).default(1),
  brief_date: BriefDateSchema,
  subject: z.string().max(44),
  preheader: z.string().max(60),
  editorial: z.string().max(220).default(""),
  intro_bullets: z.array(z.string()).min(1).max(4),
  today_ai: OptionalDigestSectionSchema,
  ai_masters: OptionalDigestSectionSchema,
  ai_research: OptionalDigestSectionSchema,
  ai_engineering: OptionalDigestSectionSchema,
  agent_tools: OptionalDigestSectionSchema,
  featured: z.array(FeaturedItemSchema).max(4).default([]),
  tools: z.array(ToolSchema).max(5).default([]),
  daily_tip: DailyTipSchema.nullish().transform((value) => value ?? null),
  quick_hits: z.array(QuickHitSchema).max(6).default([]),
  yesterday_top: YesterdayTopSchema.nullish().transform(
    (value) => value ?? null,
  ),
  model: z.string().nullish().transform((value) => value ?? null),
  stage1_stats: Stage1StatsSchema.nullish().transform(
    (value) => value ?? null,
  ),
}).superRefine((content, context) => {
  if (content.version !== 2) return;
  if (content.ai_engineering) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "v2 content cannot include AI engineering",
      path: ["ai_engineering"],
    });
  }
  if (content.featured.length > 0) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "v2 content cannot include featured items",
      path: ["featured"],
    });
  }
  if (
    content.tools.length > 0 ||
    content.daily_tip ||
    content.quick_hits.length > 0 ||
    content.yesterday_top
  ) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "v2 content cannot include legacy auxiliary sections",
      path: ["tools"],
    });
  }
});

export type AiBriefContent = z.infer<typeof AiBriefContentSchema>;

export interface AiBriefSummary {
  briefDate: string;
  subject: string;
  preheader: string;
  editorial: string;
  modules: string[];
  publishedAt: string;
}

export interface AiPublishedBrief {
  briefDate: string;
  content: AiBriefContent;
  publishedAt: string;
}

export interface AiPublishedBriefDate {
  briefDate: string;
  publishedAt: string;
}

const PublishedBriefRowSchema = z.object({
  brief_date: BriefDateSchema,
  content: AiBriefContentSchema,
  published_at: z.string().datetime({ offset: true }),
});

const NeighborRowSchema = z.object({
  brief_date: BriefDateSchema,
});

const PublishedBriefDateRowSchema = z.object({
  brief_date: BriefDateSchema,
  published_at: z.string().datetime({ offset: true }),
});

function parsePublishedBrief(row: unknown): AiPublishedBrief | null {
  const parsed = PublishedBriefRowSchema.safeParse(row);
  if (!parsed.success || parsed.data.brief_date !== parsed.data.content.brief_date) {
    return null;
  }

  return {
    briefDate: parsed.data.brief_date,
    content: parsed.data.content,
    publishedAt: parsed.data.published_at,
  };
}

function moduleLabels(content: AiBriefContent): string[] {
  const labels = (content.version === 2
    ? [
        content.today_ai && "今日AI",
        content.ai_masters && "AI大神",
        content.ai_research && "AI研究",
        content.agent_tools && "Agent工具",
      ]
    : [
        content.today_ai && "今日AI",
        content.ai_masters && "AI大神",
        content.ai_research && "AI研究",
        content.ai_engineering && "AI工程",
        content.agent_tools && "Agent工具",
      ]).filter((label): label is string => Boolean(label));

  if (content.version !== 2) {
    for (const item of content.featured) {
      if (!labels.includes(item.theme_label)) labels.push(item.theme_label);
    }
  }

  return labels;
}

function listLimit(limit: number): number {
  if (!Number.isFinite(limit)) return MAX_PUBLISHED_BRIEFS;
  return Math.min(MAX_PUBLISHED_BRIEFS, Math.max(1, Math.trunc(limit)));
}

export async function listPublishedBriefs(
  limit = MAX_PUBLISHED_BRIEFS,
): Promise<AiBriefSummary[]> {
  const { data, error } = await getSupabaseAdmin()
    .from("ai_daily_briefs")
    .select("brief_date, content, published_at")
    .eq("status", "published")
    .order("published_at", { ascending: false })
    .order("brief_date", { ascending: false })
    .limit(listLimit(limit));

  if (error || !Array.isArray(data)) {
    throw new Error("Published brief list unavailable");
  }

  return data.flatMap((row) => {
    const brief = parsePublishedBrief(row);
    if (!brief) return [];

    return [
      {
        briefDate: brief.briefDate,
        subject: brief.content.subject,
        preheader: brief.content.preheader,
        editorial: brief.content.editorial,
        modules: moduleLabels(brief.content),
        publishedAt: brief.publishedAt,
      },
    ];
  });
}

export async function listPublishedBriefDates(): Promise<
  AiPublishedBriefDate[]
> {
  try {
    const admin = getSupabaseAdmin();
    const rows: unknown[] = [];

    for (let offset = 0; ; offset += PUBLISHED_DATE_PAGE_SIZE) {
      const { data, error } = await admin
        .from("ai_daily_briefs")
        .select("brief_date, published_at")
        .eq("status", "published")
        .order("published_at", { ascending: false })
        .order("brief_date", { ascending: false })
        .range(offset, offset + PUBLISHED_DATE_PAGE_SIZE - 1);

      if (error || !Array.isArray(data)) {
        throw new Error("Published brief date query failed");
      }

      rows.push(...data);
      if (data.length < PUBLISHED_DATE_PAGE_SIZE) break;
    }

    return rows.flatMap((row) => {
      const parsed = PublishedBriefDateRowSchema.safeParse(row);
      if (!parsed.success) return [];

      return [
        {
          briefDate: parsed.data.brief_date,
          publishedAt: parsed.data.published_at,
        },
      ];
    });
  } catch {
    throw new Error("Published brief dates unavailable");
  }
}

export async function getPublishedBrief(
  date: string,
): Promise<AiPublishedBrief | null> {
  if (!isBriefDate(date)) return null;

  try {
    const { data, error } = await getSupabaseAdmin()
      .from("ai_daily_briefs")
      .select("brief_date, content, published_at")
      .eq("status", "published")
      .eq("brief_date", date)
      .maybeSingle();

    if (error) throw new Error("Published brief query failed");
    if (!data) return null;
    return parsePublishedBrief(data);
  } catch {
    throw new Error("Published brief unavailable");
  }
}

function parseNeighbor(data: unknown): string | null {
  const parsed = NeighborRowSchema.safeParse(data);
  return parsed.success ? parsed.data.brief_date : null;
}

export async function getPublishedNeighbors(date: string): Promise<{
  previous: string | null;
  next: string | null;
}> {
  if (!isBriefDate(date)) return { previous: null, next: null };

  try {
    const admin = getSupabaseAdmin();
    const [previousResult, nextResult] = await Promise.all([
      admin
        .from("ai_daily_briefs")
        .select("brief_date")
        .eq("status", "published")
        .lt("brief_date", date)
        .order("brief_date", { ascending: false })
        .limit(1)
        .maybeSingle(),
      admin
        .from("ai_daily_briefs")
        .select("brief_date")
        .eq("status", "published")
        .gt("brief_date", date)
        .order("brief_date", { ascending: true })
        .limit(1)
        .maybeSingle(),
    ]);

    if (previousResult.error || nextResult.error) {
      throw new Error("Published brief neighbor query failed");
    }

    return {
      previous: parseNeighbor(previousResult.data),
      next: parseNeighbor(nextResult.data),
    };
  } catch {
    throw new Error("Published brief neighbors unavailable");
  }
}
