import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  from: vi.fn(),
  getSupabaseAdmin: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("@/lib/supabase", () => ({
  getSupabaseAdmin: mocks.getSupabaseAdmin,
}));

import {
  AiBriefContentSchema,
  getPublishedBrief,
  getPublishedNeighbors,
  isBriefDate,
  listPublishedBriefDates,
  listPublishedBriefs,
} from "@/lib/ai-briefs";
import { siteBaseUrl } from "@/lib/site-url";

type QueryResponse = {
  data: unknown;
  error: unknown;
};

class QueryBuilder implements PromiseLike<QueryResponse> {
  readonly select = vi.fn((_columns: string) => this);
  readonly eq = vi.fn((_column: string, _value: unknown) => this);
  readonly lt = vi.fn((_column: string, _value: unknown) => this);
  readonly gt = vi.fn((_column: string, _value: unknown) => this);
  readonly order = vi.fn(
    (_column: string, _options: { ascending: boolean }) => this,
  );
  readonly limit = vi.fn((_limit: number) => this);
  readonly range = vi.fn((_from: number, _to: number) => this);
  readonly maybeSingle = vi.fn(async () => this.response);

  constructor(private readonly response: QueryResponse) {}

  then<TResult1 = QueryResponse, TResult2 = never>(
    onfulfilled?:
      | ((value: QueryResponse) => TResult1 | PromiseLike<TResult1>)
      | null,
    onrejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null,
  ): PromiseLike<TResult1 | TResult2> {
    return Promise.resolve(this.response).then(onfulfilled, onrejected);
  }
}

function useQueries(...builders: QueryBuilder[]) {
  const queue = [...builders];
  mocks.from.mockImplementation(() => queue.shift());
}

function section(
  theme:
    | "model_research"
    | "product_tools"
    | "ai_research"
    | "ai_engineering"
    | "agent_tools",
  overrides: Record<string, unknown> = {},
) {
  return {
    theme,
    header_image: "https://cdn.example.com/header.png",
    header_image_alt: "Header",
    subtitle: "Section subtitle",
    cta_label: "Read",
    stories: [
      {
        headline: "Story headline",
        summary: "Story summary",
        url: "https://example.com/story",
        label: "Source",
      },
    ],
    ...overrides,
  };
}

function content(overrides: Record<string, unknown> = {}) {
  return {
    version: 1,
    brief_date: "2026-08-03",
    subject: "Published subject",
    preheader: "Published preheader",
    editorial: "Published editorial",
    intro_bullets: ["First point"],
    today_ai: section("model_research"),
    ai_masters: null,
    ai_research: null,
    ai_engineering: null,
    agent_tools: null,
    featured: [],
    tools: [],
    daily_tip: null,
    quick_hits: [],
    yesterday_top: null,
    model: "test-model",
    stage1_stats: null,
    ...overrides,
  };
}

function row(
  briefDate: string,
  publishedAt: string,
  storedContent: Record<string, unknown> = content({ brief_date: briefDate }),
) {
  return {
    brief_date: briefDate,
    content: storedContent,
    published_at: publishedAt,
  };
}

describe("isBriefDate", () => {
  it.each(["2026-08-03", "2024-02-29"])("accepts canonical date %s", (value) => {
    expect(isBriefDate(value)).toBe(true);
  });

  it.each([
    "2026-8-03",
    "2026-08-3",
    "2026-02-29",
    "2026-04-31",
    "not-a-date",
    "",
  ])("rejects malformed or impossible date %s", (value) => {
    expect(isBriefDate(value)).toBe(false);
  });
});

describe("AiBriefContentSchema", () => {
  it("accepts both historical v1 and four-module v2 content", () => {
    expect(AiBriefContentSchema.parse(content()).version).toBe(1);
    expect(
      AiBriefContentSchema.parse(
        content({ version: 2, ai_engineering: null }),
      ).version,
    ).toBe(2);
  });

  it("rejects v2 content that still contains engineering data", () => {
    const parsed = AiBriefContentSchema.safeParse(
      content({
        version: 2,
        ai_engineering: section("ai_engineering"),
        featured: [
          {
            theme: "ai_engineering",
            theme_label: "AI工程",
            headline: "不应持久化的工程内容",
            details: ["工程详情"],
            significance: "工程意义",
            url: "https://example.com/engineering-featured",
            source_name: "工程来源",
            og_image: null,
            article_id: "engineering-featured",
          },
        ],
      }),
    );

    expect(parsed.success).toBe(false);
  });
});

describe("published brief queries", () => {
  beforeEach(() => {
    mocks.getSupabaseAdmin.mockReturnValue({ from: mocks.from });
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  it("lists validated summaries newest-first with a default limit of six", async () => {
    const query = new QueryBuilder({
      data: [
        row("2026-08-03", "2026-08-03T00:00:00.000Z"),
        row(
          "2026-08-02",
          "2026-08-02T00:00:00.000Z",
          content({
            brief_date: "2026-08-02",
            subject: "Older subject",
            today_ai: null,
            ai_masters: null,
          }),
        ),
      ],
      error: null,
    });
    useQueries(query);

    const result = await listPublishedBriefs();

    expect(result).toEqual([
      {
        briefDate: "2026-08-03",
        subject: "Published subject",
        preheader: "Published preheader",
        editorial: "Published editorial",
        modules: ["今日AI"],
        publishedAt: "2026-08-03T00:00:00.000Z",
      },
      {
        briefDate: "2026-08-02",
        subject: "Older subject",
        preheader: "Published preheader",
        editorial: "Published editorial",
        modules: [],
        publishedAt: "2026-08-02T00:00:00.000Z",
      },
    ]);
    expect(query.eq).toHaveBeenCalledWith("status", "published");
    expect(query.order).toHaveBeenNthCalledWith(1, "published_at", {
      ascending: false,
    });
    expect(query.order).toHaveBeenNthCalledWith(2, "brief_date", {
      ascending: false,
    });
    expect(query.limit).toHaveBeenCalledWith(6);
  });

  it("lists v2 summaries without the retired engineering module", async () => {
    const query = new QueryBuilder({
      data: [
        row(
          "2026-08-03",
          "2026-08-03T00:00:00.000Z",
          content({
            version: 2,
            ai_masters: section("product_tools"),
            ai_research: section("ai_research"),
            agent_tools: section("agent_tools"),
          }),
        ),
      ],
      error: null,
    });
    useQueries(query);

    await expect(listPublishedBriefs()).resolves.toMatchObject([
      { modules: ["今日AI", "AI大神", "AI研究", "Agent工具"] },
    ]);
  });

  it("caps an explicit list limit at six and drops malformed whole rows", async () => {
    const query = new QueryBuilder({
      data: [
        row("2026-08-03", "2026-08-03T00:00:00.000Z"),
        row(
          "2026-08-02",
          "2026-08-02T00:00:00.000Z",
          content({ brief_date: "2026-08-02", intro_bullets: [] }),
        ),
      ],
      error: null,
    });
    useQueries(query);

    const result = await listPublishedBriefs(100);

    expect(result.map((brief) => brief.briefDate)).toEqual(["2026-08-03"]);
    expect(query.limit).toHaveBeenCalledWith(6);
  });

  it("rejects list query failures without exposing the raw database error", async () => {
    const query = new QueryBuilder({
      data: null,
      error: { message: "connection failed with secret-token-123" },
    });
    useQueries(query);

    const request = listPublishedBriefs();

    await expect(request).rejects.toThrow("Published brief list unavailable");
    await expect(request).rejects.not.toThrow("secret-token-123");
  });

  it("lists every valid published date newest-first for public discovery", async () => {
    const query = new QueryBuilder({
      data: [
        {
          brief_date: "2026-08-03",
          published_at: "2026-08-03T01:30:00.000Z",
        },
        {
          brief_date: "2026-08-02",
          published_at: "2026-08-02T01:30:00.000Z",
        },
        {
          brief_date: "2026-02-29",
          published_at: "2026-02-28T01:30:00.000Z",
        },
      ],
      error: null,
    });
    useQueries(query);

    await expect(listPublishedBriefDates()).resolves.toEqual([
      {
        briefDate: "2026-08-03",
        publishedAt: "2026-08-03T01:30:00.000Z",
      },
      {
        briefDate: "2026-08-02",
        publishedAt: "2026-08-02T01:30:00.000Z",
      },
    ]);
    expect(query.select).toHaveBeenCalledWith("brief_date, published_at");
    expect(query.eq).toHaveBeenCalledWith("status", "published");
    expect(query.order).toHaveBeenNthCalledWith(1, "published_at", {
      ascending: false,
    });
    expect(query.order).toHaveBeenNthCalledWith(2, "brief_date", {
      ascending: false,
    });
    expect(query.limit).not.toHaveBeenCalled();
    expect(query.range).toHaveBeenCalledWith(0, 999);
  });

  it("paginates published dates without changing their global order", async () => {
    const firstPageRows = Array.from({ length: 1000 }, (_, index) => ({
      brief_date: index === 0 ? "2026-08-03" : "2026-08-02",
      published_at:
        index === 0
          ? "2026-08-03T01:30:00.000Z"
          : "2026-08-02T01:30:00.000Z",
    }));
    const firstPage = new QueryBuilder({ data: firstPageRows, error: null });
    const secondPage = new QueryBuilder({
      data: [
        {
          brief_date: "2026-08-01",
          published_at: "2026-08-01T01:30:00.000Z",
        },
      ],
      error: null,
    });
    useQueries(firstPage, secondPage);

    const result = await listPublishedBriefDates();

    expect(result).toHaveLength(1001);
    expect(result[0]).toEqual({
      briefDate: "2026-08-03",
      publishedAt: "2026-08-03T01:30:00.000Z",
    });
    expect(result[999]).toEqual({
      briefDate: "2026-08-02",
      publishedAt: "2026-08-02T01:30:00.000Z",
    });
    expect(result[1000]).toEqual({
      briefDate: "2026-08-01",
      publishedAt: "2026-08-01T01:30:00.000Z",
    });
    expect(firstPage.range).toHaveBeenCalledWith(0, 999);
    expect(secondPage.range).toHaveBeenCalledWith(1000, 1999);
    for (const query of [firstPage, secondPage]) {
      expect(query.order).toHaveBeenNthCalledWith(1, "published_at", {
        ascending: false,
      });
      expect(query.order).toHaveBeenNthCalledWith(2, "brief_date", {
        ascending: false,
      });
    }
  });

  it("sanitizes a later discovery-page failure", async () => {
    const firstPage = new QueryBuilder({
      data: Array.from({ length: 1000 }, () => ({
        brief_date: "2026-08-03",
        published_at: "2026-08-03T01:30:00.000Z",
      })),
      error: null,
    });
    const secondPage = new QueryBuilder({
      data: null,
      error: { message: "page two failed with service-role-secret" },
    });
    useQueries(firstPage, secondPage);

    const request = listPublishedBriefDates();

    await expect(request).rejects.toThrow("Published brief dates unavailable");
    await expect(request).rejects.not.toThrow("service-role-secret");
  });

  it("rejects discovery outages with a fixed non-sensitive error", async () => {
    const query = new QueryBuilder({
      data: null,
      error: { message: "sitemap failed with service-role-secret" },
    });
    useQueries(query);

    const request = listPublishedBriefDates();

    await expect(request).rejects.toThrow("Published brief dates unavailable");
    await expect(request).rejects.not.toThrow("service-role-secret");
  });

  it("sanitizes discovery client-construction failures", async () => {
    mocks.getSupabaseAdmin.mockImplementationOnce(() => {
      throw new Error("auth failed with sitemap-service-secret");
    });

    const request = listPublishedBriefDates();

    await expect(request).rejects.toThrow("Published brief dates unavailable");
    await expect(request).rejects.not.toThrow("sitemap-service-secret");
  });

  it("returns a complete brief and sanitizes optional non-HTTPS URLs", async () => {
    const stored = content({
      ai_masters: section("product_tools"),
      ai_research: section("ai_research"),
      ai_engineering: section("ai_engineering", {
        header_image: "http://unsafe.example/header.png",
      }),
      agent_tools: section("agent_tools", {
        stories: [
          {
            headline: "Agent tool",
            summary: "Tool summary",
            url: "javascript:alert(1)",
            label: "Tool",
          },
        ],
      }),
      featured: [
        {
          theme: "model_research",
          theme_label: "模型研究",
          headline: "Featured headline",
          details: ["Detail"],
          significance: "Why it matters",
          url: "https://example.com/featured",
          source_name: "Example",
          og_image: "http://unsafe.example/image.png",
          article_id: "article-1",
        },
      ],
      quick_hits: [{ text: "Quick hit", url: "ftp://unsafe.example/item" }],
    });
    const query = new QueryBuilder({
      data: row("2026-08-03", "2026-08-03T00:00:00.000Z", stored),
      error: null,
    });
    useQueries(query);

    const result = await getPublishedBrief("2026-08-03");

    expect(result?.content.ai_engineering?.header_image).toBeNull();
    expect(result?.content.agent_tools?.stories[0].url).toBe("");
    expect(result?.content.featured[0].og_image).toBeNull();
    expect(result?.content.quick_hits[0].url).toBeUndefined();
    expect(query.eq).toHaveBeenCalledWith("status", "published");
    expect(query.eq).toHaveBeenCalledWith("brief_date", "2026-08-03");
  });

  it("rejects malformed content as a whole", async () => {
    const query = new QueryBuilder({
      data: row(
        "2026-08-03",
        "2026-08-03T00:00:00.000Z",
        content({ intro_bullets: [] }),
      ),
      error: null,
    });
    useQueries(query);

    await expect(getPublishedBrief("2026-08-03")).resolves.toBeNull();
  });

  it("rejects a detail query failure without exposing the raw database error", async () => {
    const query = new QueryBuilder({
      data: null,
      error: { message: "detail failed with secret-token-123" },
    });
    useQueries(query);

    const request = getPublishedBrief("2026-08-03");

    await expect(request).rejects.toThrow("Published brief unavailable");
    await expect(request).rejects.not.toThrow("secret-token-123");
  });

  it("sanitizes service-client construction failures", async () => {
    mocks.getSupabaseAdmin.mockImplementationOnce(() => {
      throw new Error("auth failed with service-role-secret");
    });

    const request = getPublishedBrief("2026-08-03");

    await expect(request).rejects.toThrow("Published brief unavailable");
    await expect(request).rejects.not.toThrow("service-role-secret");
  });

  it("does not query for an invalid date", async () => {
    await expect(getPublishedBrief("2026-02-29")).resolves.toBeNull();
    expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
  });

  it("selects the closest published previous and next dates", async () => {
    const previous = new QueryBuilder({
      data: { brief_date: "2026-08-02" },
      error: null,
    });
    const next = new QueryBuilder({
      data: { brief_date: "2026-08-04" },
      error: null,
    });
    useQueries(previous, next);

    const result = await getPublishedNeighbors("2026-08-03");

    expect(result).toEqual({ previous: "2026-08-02", next: "2026-08-04" });
    for (const query of [previous, next]) {
      expect(query.eq).toHaveBeenCalledWith("status", "published");
      expect(query.limit).toHaveBeenCalledWith(1);
    }
    expect(previous.lt).toHaveBeenCalledWith("brief_date", "2026-08-03");
    expect(previous.order).toHaveBeenCalledWith("brief_date", {
      ascending: false,
    });
    expect(next.gt).toHaveBeenCalledWith("brief_date", "2026-08-03");
    expect(next.order).toHaveBeenCalledWith("brief_date", { ascending: true });
  });

  it("rejects neighbor query failures instead of projecting missing dates", async () => {
    const previous = new QueryBuilder({
      data: null,
      error: { message: "neighbor failed with secret-token-456" },
    });
    const next = new QueryBuilder({ data: null, error: null });
    useQueries(previous, next);

    const request = getPublishedNeighbors("2026-08-03");

    await expect(request).rejects.toThrow(
      "Published brief neighbors unavailable",
    );
    await expect(request).rejects.not.toThrow("secret-token-456");
  });
});

describe("siteBaseUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("keeps the canonical production fallback", () => {
    vi.stubEnv("WEB_BASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_WEB_BASE_URL", "");

    expect(siteBaseUrl()).toBe("https://aivizens.com");
  });

  it("prefers the server base URL", () => {
    vi.stubEnv("WEB_BASE_URL", "https://preview.aivizens.invalid/");
    vi.stubEnv("NEXT_PUBLIC_WEB_BASE_URL", "https://public.invalid");

    expect(siteBaseUrl()).toBe("https://preview.aivizens.invalid");
  });
});
