import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import {
  fetchCandidates,
  findCandidateByPrefix,
  humanDate,
  isValidBriefDate,
  siteBaseUrl,
} from "@/lib/briefs";
import { topicLabel } from "@/lib/topics";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = Promise<{ date: string; id: string }>;

const ID_PREFIX_RE = /^[0-9a-f]{4,32}$/i;

export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const { date, id } = await params;
  if (!isValidBriefDate(date) || !ID_PREFIX_RE.test(id)) {
    return { title: "NEV 早报" };
  }
  const candidates = await fetchCandidates(date);
  const item = candidates ? findCandidateByPrefix(candidates, id) : null;
  if (!item) return { title: "NEV 早报" };

  const base = siteBaseUrl();
  const canonical = `${base}/d/${date}/${item.cluster_id.slice(0, 8)}`;
  const title = `${item.title} · NEV 早报`;
  const description = item.summary.slice(0, 200);

  return {
    title,
    description,
    alternates: { canonical },
    robots: { index: true, follow: true },
    openGraph: {
      type: "article",
      url: canonical,
      siteName: "NEV 早报",
      title: item.title,
      description,
      locale: "zh_CN",
      images: [
        {
          url: `${base}/d/${date}/${item.cluster_id.slice(0, 8)}/opengraph-image`,
          width: 1200,
          height: 630,
          alt: item.title,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: item.title,
      description,
      images: [
        `${base}/d/${date}/${item.cluster_id.slice(0, 8)}/opengraph-image`,
      ],
    },
  };
}

export default async function ClusterDetailPage({
  params,
}: {
  params: Params;
}) {
  const { date, id } = await params;
  if (!isValidBriefDate(date) || !ID_PREFIX_RE.test(id)) notFound();

  const candidates = await fetchCandidates(date);
  if (!candidates) notFound();

  const item = findCandidateByPrefix(candidates, id);
  if (!item) notFound();

  const keyData = item.key_data;
  const keyDataRows: { label: string; value: string }[] = [];
  if (
    keyData?.type === "sales" &&
    Array.isArray((keyData.values as { brand_sales?: unknown })?.brand_sales)
  ) {
    const bs = (keyData.values as { brand_sales: unknown[] }).brand_sales;
    for (const r of bs) {
      if (typeof r !== "object" || r === null) continue;
      const row = r as Record<string, unknown>;
      const brand = typeof row.brand === "string" ? row.brand : "—";
      const units =
        typeof row.units === "number"
          ? row.units.toLocaleString("en-US")
          : "—";
      const period = typeof row.period === "string" ? row.period : "";
      const yoy =
        typeof row.yoy_pct === "number"
          ? ` (${row.yoy_pct > 0 ? "+" : ""}${row.yoy_pct}% YoY)`
          : "";
      keyDataRows.push({
        label: brand,
        value: `${units} 辆${period ? ` · ${period}` : ""}${yoy}`,
      });
    }
  } else if (keyData?.values) {
    for (const [k, v] of Object.entries(keyData.values)) {
      if (v == null) continue;
      keyDataRows.push({ label: k, value: String(v) });
    }
  }

  return (
    <main className="min-h-screen px-6 py-12 bg-gray-50">
      <div className="max-w-3xl mx-auto">
        <nav className="text-sm mb-6">
          <Link href={`/d/${date}`} className="text-nev-blue hover:underline">
            ← 返回 {humanDate(date)} 早报
          </Link>
        </nav>

        <article className="bg-white rounded-lg border border-gray-100 shadow-sm p-8">
          <div className="flex flex-wrap gap-1.5 mb-4">
            {item.topics.slice(0, 5).map((t) => (
              <span
                key={t}
                className="text-xs px-2 py-0.5 rounded bg-nev-green/10 text-nev-green"
              >
                #{topicLabel(t)}
              </span>
            ))}
            {item.brands.slice(0, 4).map((b) => (
              <span
                key={b}
                className="text-xs px-2 py-0.5 rounded bg-nev-blue/10 text-nev-blue"
              >
                {b}
              </span>
            ))}
          </div>

          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-4">
            {item.title}
          </h1>

          <p className="text-base text-gray-800 leading-relaxed mb-6 whitespace-pre-wrap">
            {item.summary}
          </p>

          {keyDataRows.length > 0 && (
            <div className="bg-gray-50 rounded-lg p-4 mb-6">
              <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">
                关键数据
              </div>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm">
                {keyDataRows.map((row, i) => (
                  <div key={i} className="flex justify-between">
                    <dt className="text-gray-600">{row.label}</dt>
                    <dd className="font-mono text-gray-900">{row.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          <div className="border-t border-gray-100 pt-4">
            <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">
              来源（{item.source_count}）
            </div>
            <ul className="space-y-1.5 text-sm">
              {item.source_links.map((s) => (
                <li key={s.url}>
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-nev-blue hover:underline break-all"
                  >
                    {s.name} →
                  </a>
                </li>
              ))}
            </ul>
            {item.primary_source && (
              <p className="text-xs text-gray-400 mt-3">
                权威源：{item.primary_source}
              </p>
            )}
          </div>
        </article>

        <footer className="mt-8 text-center text-xs text-gray-400">
          <Link href="/" className="hover:text-nev-blue">
            订阅每日 NEV 早报 →
          </Link>
        </footer>
      </div>
    </main>
  );
}
