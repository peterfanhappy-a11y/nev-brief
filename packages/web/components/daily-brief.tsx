import React from "react";

import type { AiBriefContent, AiPublishedBrief } from "@/lib/ai-briefs";

type DigestSection = NonNullable<AiBriefContent["today_ai"]>;
type DigestSectionEntry = {
  slotId: string;
  title: string;
  section: DigestSection | null;
};

function visibleDigestSections(content: AiBriefContent): DigestSectionEntry[] {
  if (content.version === 3) {
    return [
      { slotId: "today-ai", title: "二、今日AI", section: content.today_ai },
      { slotId: "ai-masters", title: "三、AI大神", section: content.ai_masters },
      { slotId: "ai-research", title: "四、AI研究", section: content.ai_research },
      { slotId: "agent-tools", title: "五、Agent工具", section: content.agent_tools },
    ];
  }
  return content.version === 2
    ? [
        { slotId: "today-ai", title: "一、今日AI", section: content.today_ai },
        { slotId: "ai-masters", title: "二、AI大神", section: content.ai_masters },
        { slotId: "ai-research", title: "三、AI研究", section: content.ai_research },
        { slotId: "agent-tools", title: "四、Agent工具", section: content.agent_tools },
      ]
    : [
        { slotId: "today-ai", title: "今日AI", section: content.today_ai },
        { slotId: "ai-masters", title: "AI大神", section: content.ai_masters },
        { slotId: "ai-research", title: "AI研究", section: content.ai_research },
        {
          slotId: "ai-engineering",
          title: "AI工程",
          section: content.ai_engineering,
        },
        { slotId: "agent-tools", title: "Agent工具", section: content.agent_tools },
      ];
}

function visibleFeatured(content: AiBriefContent) {
  return content.version === 2 ? [] : content.featured;
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
  slotId,
  title,
  section,
}: {
  slotId: string;
  title: string;
  section: DigestSection;
}) {
  const imageAlt = section.header_image_alt.trim() || `${title} 配图`;
  const headingId = `daily-section-${slotId}`;

  return (
    <section
      className="mt-6 overflow-hidden rounded-xl border-2 border-gray-900 bg-white"
      aria-labelledby={headingId}
    >
      <h3
        id={headingId}
        className="px-5 pt-4 text-sm font-extrabold tracking-wider text-indigo-600"
      >
        {title}
      </h3>
      {section.header_image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={section.header_image}
          alt={imageAlt}
          loading="lazy"
          className="mt-4 block h-auto w-full"
        />
      )}
      {section.subtitle && (
        <p className="px-5 pt-4 text-lg font-extrabold leading-relaxed text-gray-900">
          {section.subtitle}
        </p>
      )}
      <div className="mt-4 divide-y divide-gray-200 border-t border-gray-200">
        {section.stories.map((story, storyIndex) => (
          <div key={`${slotId}-story-${storyIndex}`} className="px-5 py-5">
            {story.label && (
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
                {story.label}
              </p>
            )}
            {section.theme === "ai_engineering" ? (
              <h3 className="text-lg font-semibold text-gray-900">
                {storyIndex + 1}. {story.headline.split("：", 1)[0]}：
                {story.headline.includes("：") && (
                  <>
                    <br />
                    {story.headline.slice(story.headline.indexOf("：") + 1).trim()}
                  </>
                )}
              </h3>
            ) : (
              <h3 className="text-lg font-semibold text-gray-900">
                {storyIndex + 1}. {story.headline}
              </h3>
            )}
            <p className="mt-2 leading-relaxed text-gray-700">{story.summary}</p>
            {story.url && (
              <p className="mt-3 text-sm font-medium">
                <ExternalLink href={story.url}>
                  {section.cta_label}<span aria-hidden="true"> →</span>
                </ExternalLink>
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function OpcBlock({ opc }: { opc: NonNullable<AiBriefContent["opc_case"]> }) {
  return (
    <section
      className="mt-6 overflow-hidden rounded-xl border-2 border-gray-900 bg-white"
      aria-labelledby="daily-section-opc-case"
    >
      <h3
        id="daily-section-opc-case"
        className="px-5 pt-4 text-sm font-extrabold tracking-wider text-indigo-600"
      >
        一、OPC案例
      </h3>
      <p className="mt-2 px-5 text-sm text-gray-500">分享者：{opc.sharer}</p>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={opc.header_image}
        alt={opc.header_image_alt}
        loading="lazy"
        className="mt-4 block h-auto w-full"
      />
      <div className="p-5">
        <h3 className="text-lg font-semibold text-gray-900">{opc.headline}</h3>
        <p className="mt-2 leading-relaxed text-gray-700">{opc.summary}</p>
        <p className="mt-2 font-semibold text-gray-900">{opc.revenue_display}</p>
        <p className="mt-3 text-sm font-medium">
          <ExternalLink href={opc.url}>
            阅读原文<span aria-hidden="true"> →</span>
          </ExternalLink>
        </p>
      </div>
    </section>
  );
}

function SectionGroupTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mt-10 bg-gray-950 px-4 py-3 text-center text-sm font-extrabold tracking-[0.35em] text-white">
      {children}
    </h2>
  );
}

export default function DailyBrief({ brief }: { brief: AiPublishedBrief }) {
  const { content } = brief;
  const featured = visibleFeatured(content);
  const digestSections = visibleDigestSections(content);

  return (
    <article className="bg-white px-1 py-2 sm:px-4 sm:py-4">
      <section
        aria-labelledby="daily-overview-heading"
        className="rounded-xl border-2 border-gray-900 bg-white p-6 sm:p-8"
      >
        <p
          id="daily-overview-heading"
          className="text-sm font-extrabold tracking-wider text-indigo-600"
        >
          概览
        </p>
        <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
          <time dateTime={brief.briefDate}>{brief.briefDate}</time>
          <span aria-hidden="true">·</span>
          <span>5 分钟阅读</span>
        </div>
        <h1 className="mt-4 text-3xl font-bold leading-tight text-gray-900 sm:text-4xl">
          {content.subject}
        </h1>
        <p className="mt-5 text-lg font-bold leading-relaxed text-gray-700">
          早上好，AI科技爱好者们！以下是今天最值得关注的 AI 洞察，5 分钟带你看懂全局。
        </p>
        {content.editorial && (
          <p className="mt-5 text-lg leading-relaxed text-gray-700">
            {content.editorial}
          </p>
        )}
        <div className="mt-6 border-t border-gray-200 pt-5 text-xs font-extrabold tracking-wider text-gray-900">
          今日 AI 简报
        </div>
        <ul className="mt-3 space-y-2 text-gray-800">
          {content.intro_bullets.map((bullet, bulletIndex) => (
            <li key={`intro-${bulletIndex}`} className="flex gap-3">
              <span className="text-indigo-500" aria-hidden="true">
                •
              </span>
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      </section>

      {content.version === 3 && content.opc_case && (
        <>
          <SectionGroupTitle>OPC分享</SectionGroupTitle>
          <OpcBlock opc={content.opc_case} />
        </>
      )}

      <SectionGroupTitle>今日精选</SectionGroupTitle>

      {digestSections.slice(0, 2).map(
        ({ slotId, title, section }) =>
          section && (
            <DigestBlock
              key={slotId}
              slotId={slotId}
              title={title}
              section={section}
            />
          ),
      )}

      {featured.length > 0 && (
        <section className="mt-6 rounded-xl border-2 border-gray-900 p-5 sm:p-6">
          <h2 className="text-xl font-bold text-gray-900">更多精选</h2>
          <div className="mt-6 space-y-8">
            {featured.map((item, itemIndex) => (
              <div key={`featured-${itemIndex}`}>
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
                  {item.details.map((detail, detailIndex) => (
                    <li key={`featured-${itemIndex}-detail-${detailIndex}`}>
                      {detail}
                    </li>
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

      <SectionGroupTitle>工具学习</SectionGroupTitle>

      {digestSections.slice(2).map(
        ({ slotId, title, section }) =>
          section && (
            <DigestBlock
              key={slotId}
              slotId={slotId}
              title={title}
              section={section}
            />
          ),
      )}

      {content.version !== 2 && content.tools.length > 0 && (
        <section className="border-t border-gray-100 py-10">
          <h2 className="text-2xl font-bold text-gray-900">AI工具</h2>
          <ul className="mt-5 space-y-4">
            {content.tools.map((tool, toolIndex) => (
              <li key={`tool-${toolIndex}`}>
                <ExternalLink href={tool.url} className="font-semibold text-indigo-600 hover:underline">
                  {tool.name}
                </ExternalLink>
                <p className="mt-1 text-sm text-gray-600">{tool.one_liner}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {content.version !== 2 && content.daily_tip && (
        <section className="border-t border-gray-100 py-10">
          <h2 className="text-2xl font-bold text-gray-900">每日技巧</h2>
          <div className="mt-5 rounded-xl bg-amber-50 p-5">
            <h3 className="font-semibold text-gray-900">{content.daily_tip.title}</h3>
            <p className="mt-2 leading-relaxed text-gray-700">{content.daily_tip.body}</p>
          </div>
        </section>
      )}

      {content.version !== 2 && content.quick_hits.length > 0 && (
        <section className="border-t border-gray-100 py-10">
          <h2 className="text-2xl font-bold text-gray-900">快讯</h2>
          <ul className="mt-5 space-y-3">
            {content.quick_hits.map((hit, hitIndex) => (
              <li key={`quick-hit-${hitIndex}`} className="text-gray-700">
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

      {content.version !== 2 && content.yesterday_top && (
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
