import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import {
  type Candidate,
  fetchCandidates,
  fetchNeighborDates,
  fetchSalesCard,
  formatUnits,
  formatYoyPct,
  humanDate,
  isValidBriefDate,
  siteBaseUrl,
} from "@/lib/briefs";
import { topicLabel } from "@/lib/topics";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = Promise<{ date: string }>;

const MAX_ITEMS = 20;

export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const { date } = await params;
  if (!isValidBriefDate(date)) return { title: "NEV 早报" };

  const candidates = await fetchCandidates(date);
  const dateHuman = humanDate(date);
  const base = siteBaseUrl();
  const canonical = `${base}/nev/d/${date}`;

  const title = `NEV 早报 · ${dateHuman}`;
  const description =
    candidates && candidates.length > 0
      ? `${dateHuman} · ${candidates.length} 条精选 — ` +
        candidates
          .slice(0, 3)
          .map((c) => c.title)
          .join("、")
      : `${dateHuman} 新能源汽车行业每日精选`;

  return {
    title,
    description,
    alternates: { canonical },
    robots: { index: true, follow: true },
    openGraph: {
      type: "article",
      url: canonical,
      siteName: "NEV 早报",
      title,
      description,
      locale: "zh_CN",
      images: [
        {
          url: `${base}/nev/d/${date}/opengraph-image`,
          width: 1200,
          height: 630,
          alt: title,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [`${base}/nev/d/${date}/opengraph-image`],
    },
  };
}

function CandidateCard({
  item,
  briefDate,
}: {
  item: Candidate;
  briefDate: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-5">
      <div className="flex flex-wrap gap-1.5 mb-2">
        {item.topics.slice(0, 4).map((t) => (
          <span
            key={t}
            className="text-xs px-2 py-0.5 rounded bg-nev-green/10 text-nev-green"
          >
            #{topicLabel(t)}
          </span>
        ))}
      </div>
      <h2 className="text-lg font-semibold text-gray-900 mb-2">
        <Link
          href={`/nev/d/${briefDate}/${item.cluster_id.slice(0, 8)}`}
          className="hover:text-nev-blue"
        >
          {item.title}
        </Link>
      </h2>
      <p className="text-sm text-gray-700 leading-relaxed mb-3">
        {item.summary}
      </p>
      <div className="text-xs text-gray-500 flex flex-wrap items-center gap-x-2 gap-y-1">
        <span>📰</span>
        {item.source_links.slice(0, 3).map((s, i) => (
          <span key={s.url} className="inline-flex items-center gap-1">
            {i > 0 && <span className="text-gray-300">/</span>}
            <a
              href={s.url}
              target="_blank"
              rel="noreferrer noopener"
              className="text-nev-blue hover:underline"
            >
              {s.name}
            </a>
          </span>
        ))}
        {item.brands.length > 0 && (
          <span className="ml-auto text-gray-400">
            {item.brands.slice(0, 4).join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}

function DayNav({
  prev,
  next,
}: {
  prev: string | null;
  next: string | null;
}) {
  return (
    <nav className="flex items-center justify-between text-sm py-4 border-t border-gray-100 mt-8">
      {prev ? (
        <Link href={`/nev/d/${prev}`} className="text-nev-blue hover:underline">
          ← 前一天 {humanDate(prev)}
        </Link>
      ) : (
        <span className="text-gray-300">← 没有更早的早报</span>
      )}
      {next ? (
        <Link href={`/nev/d/${next}`} className="text-nev-blue hover:underline">
          后一天 {humanDate(next)} →
        </Link>
      ) : (
        <span className="text-gray-300">没有更新的早报 →</span>
      )}
    </nav>
  );
}

export default async function DailyBriefPage({
  params,
}: {
  params: Params;
}) {
  const { date } = await params;
  if (!isValidBriefDate(date)) notFound();

  const [candidates, neighbors] = await Promise.all([
    fetchCandidates(date),
    fetchNeighborDates(date),
  ]);
  if (candidates === null) notFound();

  if (candidates.length === 0) {
    return (
      <main className="min-h-screen px-6 py-12">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-2xl font-bold text-gray-900">
            🚗 NEV 早报 · {humanDate(date)}
          </h1>
          <div className="mt-8 bg-white rounded-lg border border-gray-100 p-8 text-center text-gray-500">
            <div className="text-3xl mb-3">📭</div>
            当日早报尚未生成，请稍后再来。
          </div>
          <DayNav prev={neighbors.prev} next={neighbors.next} />
          <Link href="/nev" className="text-nev-blue text-sm mt-2 inline-block">
            ← 返回首页
          </Link>
        </div>
      </main>
    );
  }

  const salesCard = await fetchSalesCard(date, candidates);
  const items = candidates
    .slice()
    .sort(
      (a, b) => (b.global_importance ?? 0) - (a.global_importance ?? 0),
    )
    .slice(0, MAX_ITEMS);

  return (
    <main className="min-h-screen px-6 py-12 bg-gray-50">
      <div className="max-w-3xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">🚗 NEV 早报</h1>
          <p className="text-sm text-gray-500 mt-1">{humanDate(date)}</p>
        </header>

        {salesCard.length > 0 && (
          <section className="bg-white rounded-lg border border-gray-100 shadow-sm p-5 mb-8">
            <div className="text-sm font-semibold text-gray-700 mb-3">
              📊 销量速览（TOP {salesCard.length}）
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
              {salesCard.map((s) => (
                <div
                  key={s.brand_code}
                  className="flex items-baseline justify-between text-sm py-1 border-b border-gray-50 last:border-0"
                >
                  <span className="text-gray-800">{s.brand_name}</span>
                  <span className="font-mono">
                    {formatUnits(s.units)} 辆
                    {s.yoy != null && (
                      <span
                        className={
                          "ml-2 text-xs " +
                          (s.yoy > 0 ? "text-nev-green" : "text-gray-400")
                        }
                      >
                        {formatYoyPct(s.yoy)}
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        <div className="text-sm font-semibold text-gray-700 mb-3">
          🔥 今日 {items.length} 条
        </div>
        <div className="space-y-4">
          {items.map((item) => (
            <CandidateCard
              key={item.cluster_id}
              item={item}
              briefDate={date}
            />
          ))}
        </div>

        <DayNav prev={neighbors.prev} next={neighbors.next} />

        <footer className="mt-8 text-center text-xs text-gray-400">
          <Link href="/nev" className="hover:text-nev-blue">
            订阅每日 NEV 早报 →
          </Link>
        </footer>
      </div>
    </main>
  );
}
