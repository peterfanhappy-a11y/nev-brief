import type { Metadata } from "next";
import { notFound } from "next/navigation";
import React from "react";
import { z } from "zod";

import DailyBrief from "@/components/daily-brief";
import Footer from "@/components/footer";
import Header from "@/components/header";
import { AiBriefContentSchema } from "@/lib/ai-briefs";
import { validatePreviewToken } from "@/lib/preview-token";
import { getSupabaseAdmin } from "@/lib/supabase";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AIVIZENS 日报预览",
  robots: { index: false, follow: false },
};

const PREVIEW_STATUSES = [
  "blocked",
  "awaiting_approval",
  "approved",
  "published",
] as const;

const QualityIssueSchema = z.object({
  code: z.string(),
  path: z.string().nullable().optional(),
});

const QualityReportSchema = z.object({
  passed: z.boolean().optional(),
  blockers: z.array(QualityIssueSchema).default([]),
  warnings: z.array(QualityIssueSchema).default([]),
  metrics: z.record(z.union([z.number(), z.boolean()])).default({}),
});

const AttachmentMetadataSchema = z.object({
  filename: z.string().optional(),
  content_type: z.string().optional(),
  size_bytes: z.number().int().nonnegative().optional(),
});

const SourceMetadataSchema = z.object({
  kind: z.string().optional(),
  message_id: z.string().optional(),
  subject: z.string().optional(),
  received_at: z.string().optional(),
  requested_date: z.string().optional(),
  matched_date: z.string().optional(),
  used_fallback: z.boolean().optional(),
  attachments: z.array(AttachmentMetadataSchema).optional(),
});

const PreviewBriefRowSchema = z.object({
  brief_date: z.string(),
  content: AiBriefContentSchema,
  status: z.enum(PREVIEW_STATUSES),
  quality_report: QualityReportSchema.nullable(),
  digest_sources: z.record(SourceMetadataSchema.nullable()).nullable(),
  source_run_id: z.string().uuid().nullable(),
  model: z.string().nullable(),
  generated_at: z.string().datetime({ offset: true }),
  approved_at: z.string().datetime({ offset: true }).nullable(),
  published_at: z.string().datetime({ offset: true }).nullable(),
});

type PreviewBrief = z.infer<typeof PreviewBriefRowSchema>;
type Params = Promise<{ date: string }>;
type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function scalar(value: string | string[] | undefined): string | undefined {
  return typeof value === "string" ? value : undefined;
}

async function getPreviewBrief(date: string): Promise<PreviewBrief | null> {
  try {
    const { data, error } = await getSupabaseAdmin()
      .from("ai_daily_briefs")
      .select(
        "brief_date, content, status, quality_report, digest_sources, source_run_id, model, generated_at, approved_at, published_at",
      )
      .in("status", [...PREVIEW_STATUSES])
      .eq("brief_date", date)
      .maybeSingle();

    if (error) throw new Error("Preview brief query failed");
    if (!data) return null;
    const parsed = PreviewBriefRowSchema.safeParse(data);
    if (!parsed.success) return null;
    if (
      parsed.data.brief_date !== date ||
      parsed.data.content.brief_date !== parsed.data.brief_date
    ) {
      return null;
    }
    return parsed.data;
  } catch {
    throw new Error("Preview brief unavailable");
  }
}

function issueText(issue: z.infer<typeof QualityIssueSchema>): string {
  return issue.path ? `${issue.code} · ${issue.path}` : issue.code;
}

function ReviewEvidence({ brief }: { brief: PreviewBrief }) {
  const report = brief.quality_report;
  const sources = Object.entries(brief.digest_sources ?? {});

  return (
    <aside className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-sm text-gray-800">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold text-gray-900">只读审核预览</h2>
        <span className="rounded-full bg-amber-200 px-3 py-1 font-mono text-xs font-semibold">
          {brief.status}
        </span>
      </div>
      <dl className="mt-4 grid gap-2 sm:grid-cols-2">
        <div><dt className="font-semibold">生成模型</dt><dd>{brief.model ?? "未记录"}</dd></div>
        <div><dt className="font-semibold">来源运行 ID</dt><dd className="break-all">{brief.source_run_id ?? "未记录"}</dd></div>
        <div><dt className="font-semibold">生成时间</dt><dd>{brief.generated_at}</dd></div>
        <div><dt className="font-semibold">质量结果</dt><dd>{report?.passed === true ? "通过" : "未通过"}</dd></div>
      </dl>

      <div className="mt-5 grid gap-5 md:grid-cols-2">
        <section>
          <h3 className="font-semibold">阻断项</h3>
          {report && report.blockers.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {report.blockers.map((issue, index) => <li key={`blocker-${index}`}>{issueText(issue)}</li>)}
            </ul>
          ) : <p className="mt-2 text-gray-600">无</p>}
        </section>
        <section>
          <h3 className="font-semibold">警告项</h3>
          {report && report.warnings.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {report.warnings.map((issue, index) => <li key={`warning-${index}`}>{issueText(issue)}</li>)}
            </ul>
          ) : <p className="mt-2 text-gray-600">无</p>}
        </section>
      </div>

      <section className="mt-5">
        <h3 className="font-semibold">来源元数据</h3>
        {sources.length > 0 ? (
          <dl className="mt-2 space-y-3">
            {sources.map(([source, value]) => (
              <div key={source} className="rounded-lg bg-white/70 p-3">
                <dt className="font-mono font-semibold">{source}</dt>
                <dd className="mt-1 break-words text-gray-700">
                  {value ? JSON.stringify(value) : "缺失"}
                </dd>
              </div>
            ))}
          </dl>
        ) : <p className="mt-2 text-gray-600">未记录</p>}
      </section>
    </aside>
  );
}

export default async function PreviewPage({
  params,
  searchParams,
}: {
  params: Params;
  searchParams: SearchParams;
}) {
  const [{ date }, query] = await Promise.all([params, searchParams]);
  const expires = scalar(query.expires);
  const signature = scalar(query.signature);

  if (!validatePreviewToken({ date, expires, signature })) notFound();

  const brief = await getPreviewBrief(date);
  if (!brief) notFound();

  return (
    <main className="min-h-screen bg-gray-50">
      <Header />
      <div className="mx-auto max-w-4xl space-y-8 px-6 py-10 sm:py-14">
        <ReviewEvidence brief={brief} />
        <DailyBrief
          brief={{
            briefDate: brief.brief_date,
            content: brief.content,
            publishedAt: brief.published_at ?? brief.generated_at,
          }}
        />
      </div>
      <Footer />
    </main>
  );
}
