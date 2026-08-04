import Link from "next/link";
import React from "react";

import type { AiBriefSummary } from "@/lib/ai-briefs";

const MODULE_ACCENTS = [
  "from-indigo-500 to-violet-500",
  "from-sky-500 to-cyan-500",
  "from-emerald-500 to-teal-500",
  "from-amber-500 to-orange-500",
  "from-rose-500 to-pink-500",
] as const;

function moduleAccent(modules: string[]): string {
  if (modules.length === 0) return "from-gray-200 to-gray-300";

  const key = modules.join("|");
  const index = Array.from(key).reduce(
    (sum, character) => sum + character.codePointAt(0)!,
    0,
  );
  return MODULE_ACCENTS[index % MODULE_ACCENTS.length];
}

function BriefCard({ brief }: { brief: AiBriefSummary }) {
  const modules = brief.modules.filter((module) => module.trim().length > 0);

  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md">
      <div
        className={`h-1.5 bg-gradient-to-r ${moduleAccent(modules)}`}
        aria-hidden="true"
      />
      <div className="flex flex-1 flex-col p-5">
        <time
          dateTime={brief.briefDate}
          className="mb-3 text-xs font-medium tracking-wide text-gray-400"
        >
          {brief.briefDate}
        </time>
        <h3 className="mb-3 text-lg font-semibold leading-snug text-gray-900 transition-colors group-hover:text-indigo-600">
          <Link href={`/daily/${brief.briefDate}`}>{brief.subject}</Link>
        </h3>
        <p className="mb-5 flex-1 text-sm leading-relaxed text-gray-600">
          {brief.editorial}
        </p>
        {modules.length > 0 && (
          <ul
            className="flex flex-wrap gap-2 border-t border-gray-50 pt-4"
            aria-label="本期栏目"
          >
            {modules.map((module) => (
              <li
                key={module}
                className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600"
              >
                {module}
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}

export default function LatestBriefsGrid({
  briefs,
  unavailable = false,
}: {
  briefs: AiBriefSummary[];
  unavailable?: boolean;
}) {
  const visibleBriefs = briefs.slice(0, 6);

  return (
    <section className="mx-auto max-w-6xl px-6 py-16">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-gray-900">最新日报</h2>
        <p className="mt-1 text-sm text-gray-500">
          每天一份精选 AI 动态，讲清发生了什么、为什么重要
        </p>
      </div>

      {unavailable ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/70 px-6 py-12 text-center">
          <h3 className="text-xl font-semibold text-gray-900">
            日报暂时无法加载
          </h3>
          <p className="mx-auto mt-3 max-w-lg text-sm leading-relaxed text-gray-600">
            请稍后再试。你仍然可以订阅，日报恢复后会直接发送到邮箱。
          </p>
          <Link
            href="#subscribe"
            className="mt-6 inline-flex rounded-md bg-gray-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-gray-800"
          >
            免费订阅
          </Link>
        </div>
      ) : visibleBriefs.length > 0 ? (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {visibleBriefs.map((brief) => (
            <BriefCard key={brief.briefDate} brief={brief} />
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-indigo-200 bg-indigo-50/60 px-6 py-12 text-center">
          <h3 className="text-xl font-semibold text-gray-900">
            第一期日报正在准备中
          </h3>
          <p className="mx-auto mt-3 max-w-lg text-sm leading-relaxed text-gray-600">
            订阅后，首期发布时我们会直接发送到你的邮箱。
          </p>
          <Link
            href="#subscribe"
            className="mt-6 inline-flex rounded-md bg-gray-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-gray-800"
          >
            免费订阅
          </Link>
        </div>
      )}
    </section>
  );
}
