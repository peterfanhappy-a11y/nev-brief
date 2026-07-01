import type { MetadataRoute } from "next";
import { getSupabaseAdmin } from "@/lib/supabase";
import { siteBaseUrl } from "@/lib/briefs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteBaseUrl();
  const sb = getSupabaseAdmin();

  // List every day's index page; skip empty days (would waste crawl budget).
  const { data } = await sb
    .from("daily_briefs")
    .select("brief_date, updated_at, candidates")
    .order("brief_date", { ascending: false })
    .limit(180); // ~6 months

  const dateEntries: MetadataRoute.Sitemap = [];
  for (const row of data ?? []) {
    const arr = (row.candidates as unknown[] | null) ?? [];
    if (arr.length === 0) continue;
    dateEntries.push({
      url: `${base}/nev/d/${row.brief_date}`,
      lastModified: row.updated_at
        ? new Date(row.updated_at as string)
        : undefined,
      changeFrequency: "daily",
      priority: 0.8,
    });
  }

  return [
    { url: base, changeFrequency: "weekly", priority: 1.0 },
    { url: `${base}/nev`, changeFrequency: "weekly", priority: 0.9 },
    ...dateEntries,
  ];
}
