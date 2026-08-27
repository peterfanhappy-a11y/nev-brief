import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vector from "../../../../ai-brief/tests/fixtures/preview-token-vector.json";
import { PUBLISHED_BRIEF_CONTENT } from "@/test/fixtures/published-brief";

const mocks = vi.hoisted(() => ({
  from: vi.fn(),
  notFound: vi.fn(),
  getSupabaseAdmin: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("@/lib/supabase", () => ({
  getSupabaseAdmin: mocks.getSupabaseAdmin,
}));
vi.mock("next/navigation", () => ({
  notFound: mocks.notFound,
}));

import PreviewPage, { metadata } from "@/app/preview/[date]/page";

type QueryResponse = { data: unknown; error: unknown };

class ReadOnlyQuery {
  readonly select = vi.fn((_columns: string) => this);
  readonly eq = vi.fn((_column: string, _value: unknown) => this);
  readonly in = vi.fn((_column: string, _values: readonly string[]) => this);
  readonly maybeSingle = vi.fn(async () => this.response);

  constructor(private readonly response: QueryResponse) {}
}

const qualityReport = {
  passed: false,
  blockers: [{ code: "subject_blank", path: "subject" }],
  warnings: [{ code: "source_fallback", path: "today_ai" }],
  metrics: { quality_passed: false, blocker_count: 1 },
};

function previewRow(status: "blocked" | "awaiting_approval" | "approved" | "published") {
  return {
    brief_date: vector.date,
    content: { ...PUBLISHED_BRIEF_CONTENT, brief_date: vector.date },
    status,
    quality_report: qualityReport,
    digest_sources: {
      events: {
        kind: "events",
        subject: "ai-events-digest-2026-08-04",
        matched_date: vector.date,
        used_fallback: false,
      },
      agent: null,
    },
    source_run_id: "31a9cf25-51f4-4e83-9c77-5574d8d6bc30",
    model: "preview-model",
    generated_at: "2026-08-04T01:00:00.000Z",
    approved_at: status === "approved" || status === "published"
      ? "2026-08-04T01:10:00.000Z"
      : null,
    published_at: status === "published" ? "2026-08-04T01:20:00.000Z" : null,
  };
}

const params = (date = vector.date) => Promise.resolve({ date });
const searchParams = (
  overrides: { expires?: string; signature?: string } = {},
) => Promise.resolve({
  expires: String(vector.expires),
  signature: vector.signature,
  ...overrides,
});

describe("signed daily brief preview", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    vi.stubEnv("PREVIEW_SIGNING_SECRET", vector.secret);
    vi.setSystemTime(new Date(vector.now * 1000));
    mocks.notFound.mockImplementation(() => {
      throw new Error("NEXT_NOT_FOUND");
    });
    mocks.getSupabaseAdmin.mockReturnValue({ from: mocks.from });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it.each([
    ["tampered date", "2026-08-05", String(vector.expires), vector.signature],
    ["tampered expiry", vector.date, String(vector.expires + 1), vector.signature],
    ["tampered signature", vector.date, String(vector.expires), `1${vector.signature.slice(1)}`],
    ["missing expiry", vector.date, undefined, vector.signature],
    ["missing signature", vector.date, String(vector.expires), undefined],
  ])(
    "rejects %s before creating a Supabase query",
    async (_case, date, expires, signature) => {
      await expect(
        PreviewPage({
          params: params(date),
          searchParams: searchParams({ expires, signature }),
        }),
      ).rejects.toThrow("NEXT_NOT_FOUND");
      expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
      expect(mocks.from).not.toHaveBeenCalled();
    },
  );

  it("rejects an expired token before querying", async () => {
    vi.setSystemTime(new Date(vector.expires * 1000));

    await expect(
      PreviewPage({ params: params(), searchParams: searchParams() }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
    expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
  });

  it("rejects a lifetime over 900 seconds before querying", async () => {
    vi.setSystemTime(new Date((vector.expires - 901) * 1000));

    await expect(
      PreviewPage({ params: params(), searchParams: searchParams() }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
    expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
  });

  it("rejects a missing secret before querying", async () => {
    vi.stubEnv("PREVIEW_SIGNING_SECRET", "");

    await expect(
      PreviewPage({ params: params(), searchParams: searchParams() }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
    expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
  });

  it.each(["blocked", "awaiting_approval", "approved", "published"] as const)(
    "renders a read-only %s brief with review and source evidence",
    async (status) => {
      const query = new ReadOnlyQuery({ data: previewRow(status), error: null });
      mocks.from.mockReturnValue(query);

      const view = render(
        await PreviewPage({ params: params(), searchParams: searchParams() }),
      );

      expect(screen.getByRole("heading", { name: "Fixture 已发布 AI 日报" })).toBeInTheDocument();
      expect(screen.getByText(status, { exact: true })).toBeInTheDocument();
      expect(screen.getByText(/subject_blank/)).toBeInTheDocument();
      expect(screen.getByText(/source_fallback/)).toBeInTheDocument();
      expect(screen.getByText(/ai-events-digest-2026-08-04/)).toBeInTheDocument();
      expect(screen.getByText(/31a9cf25-51f4-4e83-9c77-5574d8d6bc30/)).toBeInTheDocument();
      expect(screen.getByText(/preview-model/)).toBeInTheDocument();
      expect(query.in).toHaveBeenCalledWith("status", [
        "blocked",
        "awaiting_approval",
        "approved",
        "published",
      ]);
      expect(query.eq).toHaveBeenCalledWith("brief_date", vector.date);
      expect(mocks.from).toHaveBeenCalledOnce();
      expect(view.container.textContent).not.toContain(vector.signature);
      expect(view.container.textContent).not.toContain(vector.secret);
    },
  );

  it("returns not found for an absent or malformed stored preview", async () => {
    const query = new ReadOnlyQuery({ data: null, error: null });
    mocks.from.mockReturnValue(query);

    await expect(
      PreviewPage({ params: params(), searchParams: searchParams() }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("uses private crawler metadata without querying", () => {
    expect(metadata).toEqual({
      title: "AIVIZENS 日报预览",
      robots: { index: false, follow: false },
    });
    expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
  });
});
