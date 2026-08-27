import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import React from "react";

import BriefSubscribeCta from "@/components/brief-subscribe-cta";
import DailyBrief from "@/components/daily-brief";
import Footer from "@/components/footer";
import Header from "@/components/header";
import {
  getPublishedBrief,
  getPublishedNeighbors,
  isBriefDate,
} from "@/lib/ai-briefs";
import { siteBaseUrl } from "@/lib/site-url";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = Promise<{ date: string }>;

const PRIVATE_METADATA: Metadata = {
  title: "AIVIZENS 日报",
  robots: { index: false, follow: false },
};

export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const { date } = await params;
  if (!isBriefDate(date)) return PRIVATE_METADATA;

  const brief = await getPublishedBrief(date);
  if (!brief) return PRIVATE_METADATA;

  const canonical = `${siteBaseUrl()}/daily/${brief.briefDate}`;
  const title = `${brief.content.subject} · AIVIZENS 日报`;
  const description = brief.content.preheader;

  return {
    title,
    description,
    alternates: { canonical },
    robots: { index: true, follow: true },
    openGraph: {
      type: "article",
      url: canonical,
      siteName: "AIVIZENS",
      title,
      description,
      locale: "zh_CN",
      publishedTime: brief.publishedAt,
      images: [
        {
          url: `${canonical}/opengraph-image`,
          width: 1200,
          height: 630,
          alt: title,
        },
      ],
    },
  };
}

function IssueNavigation({
  previous,
  next,
}: {
  previous: string | null;
  next: string | null;
}) {
  return (
    <nav
      aria-label="日报期数导航"
      className="grid gap-4 sm:grid-cols-2"
    >
      {previous ? (
        <Link
          href={`/daily/${previous}`}
          className="rounded-xl border border-gray-200 bg-white px-5 py-4 text-sm font-medium text-gray-700 transition-colors hover:border-indigo-300 hover:text-indigo-600"
        >
          ← 上一期 {previous}
        </Link>
      ) : (
        <span className="rounded-xl border border-gray-100 px-5 py-4 text-sm text-gray-400">
          ← 没有更早的日报
        </span>
      )}
      {next ? (
        <Link
          href={`/daily/${next}`}
          className="rounded-xl border border-gray-200 bg-white px-5 py-4 text-right text-sm font-medium text-gray-700 transition-colors hover:border-indigo-300 hover:text-indigo-600"
        >
          下一期 {next} →
        </Link>
      ) : (
        <span className="rounded-xl border border-gray-100 px-5 py-4 text-right text-sm text-gray-400">
          没有更新的日报 →
        </span>
      )}
    </nav>
  );
}

export default async function DailyArchivePage({
  params,
}: {
  params: Params;
}) {
  const { date } = await params;
  if (!isBriefDate(date)) notFound();

  const brief = await getPublishedBrief(date);
  if (!brief) notFound();

  const neighbors = await getPublishedNeighbors(date);

  return (
    <main className="min-h-screen bg-gray-50">
      <Header />
      <div className="mx-auto max-w-4xl space-y-8 px-6 py-10 sm:py-14">
        <Link
          href="/"
          className="inline-flex text-sm font-medium text-indigo-600 hover:underline"
        >
          ← 返回 AIVIZENS 首页
        </Link>
        <DailyBrief brief={brief} />
        <IssueNavigation
          previous={neighbors.previous}
          next={neighbors.next}
        />
        <BriefSubscribeCta />
      </div>
      <Footer />
    </main>
  );
}
