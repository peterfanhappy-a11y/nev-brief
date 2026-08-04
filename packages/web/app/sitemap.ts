import type { MetadataRoute } from "next";

import { listPublishedBriefDates } from "@/lib/ai-briefs";
import { siteBaseUrl } from "@/lib/site-url";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteBaseUrl();
  const briefs = await listPublishedBriefDates();

  const dateEntries: MetadataRoute.Sitemap = briefs.map((brief) => ({
    url: `${base}/daily/${brief.briefDate}`,
    lastModified: new Date(brief.publishedAt),
    changeFrequency: "daily",
    priority: 0.8,
  }));

  return [
    { url: base, changeFrequency: "weekly", priority: 1.0 },
    ...dateEntries,
  ];
}
