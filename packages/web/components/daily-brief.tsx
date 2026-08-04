import React from "react";

import type { AiBriefContent, AiPublishedBrief } from "@/lib/ai-briefs";

/** A conservative reading pace for compact Chinese news prose. */
const CHINESE_CHARACTERS_PER_MINUTE = 400;

export function estimateChineseReadMinutes(text: string): number {
  const characters = Array.from(text.replace(/\s/g, "")).length;
  return Math.max(1, Math.ceil(characters / CHINESE_CHARACTERS_PER_MINUTE));
}

type DigestSection = NonNullable<AiBriefContent["today_ai"]>;

function issuePlainText(content: AiBriefContent): string {
  const parts = [
    content.subject,
    content.editorial,
    ...content.intro_bullets,
  ];

  for (const section of [
    content.today_ai,
    content.ai_masters,
    content.ai_research,
    content.ai_engineering,
    content.agent_tools,
  ]) {
    if (!section) continue;
    parts.push(section.subtitle);
    for (const story of section.stories) {
      parts.push(story.headline, story.summary, story.label);
    }
  }

  for (const item of content.featured) {
    parts.push(
      item.theme_label,
      item.headline,
      ...item.details,
      item.significance,
      item.source_name,
    );
  }
  for (const tool of content.tools) parts.push(tool.name, tool.one_liner);
  if (content.daily_tip) {
    parts.push(content.daily_tip.title, content.daily_tip.body);
  }
  for (const hit of content.quick_hits) parts.push(hit.text);
  if (content.yesterday_top) parts.push(content.yesterday_top.headline);

  return parts.join("");
}

function ExternalLink({
  href,
  children,
  className = "text-indigo-600 hover:text-indigo-700 hover:underline",
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className={className}
    >
      {children}
    </a>
  );
}

function DigestBlock({
  title,
  section,
}: {
  title: string;
  section: DigestSection;
}) {
  const imageAlt = section.header_image_alt.trim() || `${title} 配图`;

  return (
    <section className="border-t border-gray-100 py-10" aria-labelledby={`section-${section.theme}`}>
      <h2
        id={`section-${section.theme}`}
        className="text-2xl font-bold text-gray-900"
      >
        {title}
      </h2>
      {section.subtitle && (
        <p className="mt-2 text-sm leading-relaxed text-gray-500">
          {section.subtitle}
        </p>
      )}
      {section.header_image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={section.header_image}
          alt={imageAlt}
          loading="lazy"
          className="mt-6 aspect-[16/9] w-full rounded-xl object-cover"
        />
      )}
      <div className="mt-6 space-y-6">
        {section.stories.map((story) => (
          <div key={`${story.headline}-${story.url}`}>
            {story.label && (
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-indigo-600">
                {story.label}
              </p>
            )}
            <h3 className="text-lg font-semibold text-gray-900">
              {story.headline}
            </h3>
            <p className="mt-2 leading-relaxed text-gray-700">{story.summary}</p>
            {story.url && (
              <p className="mt-3 text-sm font-medium">
                <ExternalLink href={story.url}>{section.cta_label}</ExternalLink>
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

export default function DailyBrief({ brief }: { brief: AiPublishedBrief }) {
  const { content } = brief;
  const readMinutes = estimateChineseReadMinutes(issuePlainText(content));
  const digestSections: Array<{
    title: string;
    section: DigestSection | null;
  }> = [
    { title: "今日AI", section: content.today_ai },
    { title: "AI大神", section: content.ai_masters },
    { title: "AI研究", section: content.ai_research },
    { title: "AI工程", section: content.ai_engineering },
    { title: "Agent工具", section: content.agent_tools },
  ];

  return (
    <article className="rounded-2xl border border-gray-100 bg-white px-6 py-8 shadow-sm sm:px-10 sm:py-12">
      <header className="pb-10">
        <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
          <time dateTime={brief.briefDate}>{brief.briefDate}</time>
          <span aria-hidden="true">·</span>
          <span>{readMinutes} 分钟阅读</span>
        </div>
        <h1 className="mt-4 text-3xl font-bold leading-tight text-gray-900 sm:text-4xl">
          {content.subject}
        </h1>
        {content.editorial && (
          <p className="mt-5 text-lg leading-relaxed text-gray-700">
            {content.editorial}
          </p>
        )}
        <ul className="mt-6 space-y-2 rounded-xl bg-indigo-50/70 p-5 text-gray-800">
          {content.intro_bullets.map((bullet) => (
            <li key={bullet} className="flex gap-3">
              <span className="text-indigo-500" aria-hidden="true">
                •
              </span>
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      </header>

      {digestSections.map(
        ({ title, section }) =>
          section && <DigestBlock key={title} title={title} section={section} />,
      )}

      {content.featured.length > 0 && (
        <section className="border-t border-gray-100 py-10">
          <h2 className="text-2xl font-bold text-gray-900">更多精选</h2>
          <div className="mt-6 space-y-8">
            {content.featured.map((item) => (
              <div key={`${item.headline}-${item.url}`}>
                {item.og_image && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={item.og_image}
                    alt={`${item.headline} 配图`}
                    loading="lazy"
                    className="mb-5 aspect-[16/9] w-full rounded-xl object-cover"
                  />
                )}
                <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">
                  {item.theme_label}
                </p>
                <h3 className="mt-1 text-lg font-semibold text-gray-900">
                  {item.headline}
                </h3>
                <ul className="mt-3 list-disc space-y-1 pl-5 text-gray-700">
                  {item.details.map((detail) => (
                    <li key={detail}>{detail}</li>
                  ))}
                </ul>
                <p className="mt-3 leading-relaxed text-gray-700">
                  {item.significance}
                </p>
                <p className="mt-3 text-sm font-medium">
                  <ExternalLink href={item.url}>{item.source_name}</ExternalLink>
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {content.tools.length > 0 && (
        <section className="border-t border-gray-100 py-10">
          <h2 className="text-2xl font-bold text-gray-900">AI工具</h2>
          <ul className="mt-5 space-y-4">
            {content.tools.map((tool) => (
              <li key={`${tool.name}-${tool.url}`}>
                <ExternalLink href={tool.url} className="font-semibold text-indigo-600 hover:underline">
                  {tool.name}
                </ExternalLink>
                <p className="mt-1 text-sm text-gray-600">{tool.one_liner}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {content.daily_tip && (
        <section className="border-t border-gray-100 py-10">
          <h2 className="text-2xl font-bold text-gray-900">每日技巧</h2>
          <div className="mt-5 rounded-xl bg-amber-50 p-5">
            <h3 className="font-semibold text-gray-900">{content.daily_tip.title}</h3>
            <p className="mt-2 leading-relaxed text-gray-700">{content.daily_tip.body}</p>
          </div>
        </section>
      )}

      {content.quick_hits.length > 0 && (
        <section className="border-t border-gray-100 py-10">
          <h2 className="text-2xl font-bold text-gray-900">快讯</h2>
          <ul className="mt-5 space-y-3">
            {content.quick_hits.map((hit) => (
              <li key={`${hit.text}-${hit.url ?? ""}`} className="text-gray-700">
                {hit.url ? (
                  <ExternalLink href={hit.url}>{hit.text}</ExternalLink>
                ) : (
                  hit.text
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {content.yesterday_top && (
        <section className="border-t border-gray-100 pt-10">
          <h2 className="text-2xl font-bold text-gray-900">昨日焦点</h2>
          <p className="mt-4 font-medium">
            <ExternalLink href={content.yesterday_top.url}>
              {content.yesterday_top.headline}
            </ExternalLink>
          </p>
        </section>
      )}
    </article>
  );
}
