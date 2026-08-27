import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const TOKEN = "11111111-1111-4111-8111-111111111111";
const DELIVERY = "22222222-2222-4222-8222-222222222222";

const mocks = vi.hoisted(() => ({
  getSupabaseAdmin: vi.fn(),
  from: vi.fn(),
  select: vi.fn(),
  update: vi.fn(),
  upsert: vi.fn(),
  selectEq: vi.fn(),
  writeEq: vi.fn(),
  maybeSingle: vi.fn(),
  redirect: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  getSupabaseAdmin: mocks.getSupabaseAdmin,
}));
vi.mock("next/navigation", () => ({
  redirect: mocks.redirect,
}));

import { GET as legacyRatingGet } from "./api/ai/rate/route";
import { POST as oneClickUnsubscribe } from "./api/unsubscribe/route";
import RatePage from "./rate/page";
import { recordRatingAction } from "./rate/actions";
import { unsubscribeAction } from "./unsubscribe/actions";
import UnsubscribePage from "./unsubscribe/page";

function form(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) data.set(key, value);
  return data;
}

function renderServerActionPage(element: React.ReactNode) {
  const consoleError = vi.spyOn(console, "error").mockImplementation((message, ...args) => {
    if (
      !String(message).includes("Invalid value for prop") ||
      !args.some((value) => String(value).includes("action"))
    ) {
      throw new Error(`Unexpected render error: ${String(message)}`);
    }
  });
  try {
    return render(element);
  } finally {
    consoleError.mockRestore();
  }
}

describe("scanner-safe GET entry points", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    mocks.getSupabaseAdmin.mockReturnValue({ from: mocks.from });
    mocks.from.mockReturnValue({
      select: mocks.select,
      update: mocks.update,
      upsert: mocks.upsert,
    });
    mocks.select.mockReturnValue({ eq: mocks.selectEq });
    mocks.update.mockReturnValue({ eq: mocks.writeEq });
    mocks.upsert.mockResolvedValue({ error: null });
    mocks.selectEq.mockReturnValue({ maybeSingle: mocks.maybeSingle });
    mocks.writeEq.mockResolvedValue({ error: null });
    mocks.maybeSingle.mockResolvedValue({
      data: { status: "active" },
      error: null,
    });
    mocks.redirect.mockImplementation((url: string) => {
      throw new Error(`REDIRECT:${url}`);
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders the unsubscribe GET with a select and no database write", async () => {
    renderServerActionPage(
      await UnsubscribePage({
        searchParams: Promise.resolve({ token: TOKEN, product: "ai" }),
      }),
    );

    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.upsert).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "确认退订" })).toBeInTheDocument();
    expect(mocks.select).toHaveBeenCalledWith("status");
  });

  it("routes an unsubscribed reader through normal double opt-in", async () => {
    mocks.maybeSingle.mockResolvedValue({
      data: { status: "unsubscribed" },
      error: null,
    });

    renderServerActionPage(
      await UnsubscribePage({
        searchParams: Promise.resolve({ token: TOKEN, product: "ai" }),
      }),
    );

    expect(screen.getByRole("link", { name: "重新订阅" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.queryByRole("button", { name: "重新订阅" })).toBeNull();
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it("renders the rating GET without a database call", async () => {
    renderServerActionPage(
      await RatePage({
        searchParams: Promise.resolve({ delivery: DELIVERY, score: "2" }),
      }),
    );

    expect(screen.getByRole("button", { name: "提交评分" })).toBeInTheDocument();
    expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
    expect(mocks.upsert).not.toHaveBeenCalled();
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it("redirects the legacy rating GET to a read-only page without a write", async () => {
    const response = await legacyRatingGet(
      new Request(`https://aivizens.test/api/ai/rate?d=${DELIVERY}&s=3`),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      `https://aivizens.test/rate?delivery=${DELIVERY}&score=3`,
    );
    expect(mocks.upsert).not.toHaveBeenCalled();
    expect(mocks.update).not.toHaveBeenCalled();
  });
});

describe("explicit mutation actions", () => {
  beforeEach(() => {
    mocks.getSupabaseAdmin.mockReturnValue({ from: mocks.from });
    mocks.from.mockReturnValue({
      select: mocks.select,
      update: mocks.update,
      upsert: mocks.upsert,
    });
    mocks.update.mockReturnValue({ eq: mocks.writeEq });
    mocks.writeEq.mockResolvedValue({ error: null });
    mocks.upsert.mockResolvedValue({ error: null });
    mocks.redirect.mockImplementation((url: string) => {
      throw new Error(`REDIRECT:${url}`);
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("records an explicit AIVIZENS unsubscribe with its timestamp", async () => {
    await expect(unsubscribeAction(form({ token: TOKEN }))).rejects.toThrow(
      "REDIRECT:/unsubscribe?status=unsubscribed",
    );

    expect(mocks.from).toHaveBeenCalledWith("ai_subscribers");
    expect(mocks.update).toHaveBeenCalledWith({
      status: "unsubscribed",
      unsubscribed_at: expect.any(String),
    });
    expect(mocks.writeEq).toHaveBeenCalledWith("unsubscribe_token", TOKEN);
  });

  it("reports a static unsubscribe failure without leaking its token", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    mocks.writeEq.mockResolvedValue({ error: { message: `db leaked ${TOKEN}` } });

    await expect(unsubscribeAction(form({ token: TOKEN }))).rejects.toThrow(
      "REDIRECT:/unsubscribe?status=error",
    );

    expect(consoleError).toHaveBeenCalledWith("[unsubscribe] update failed");
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain(TOKEN);
    consoleError.mockRestore();
  });

  it.each([1, 2, 3])("upserts the allowed rating score %i", async (score) => {
    await expect(
      recordRatingAction(form({ delivery: DELIVERY, score: String(score) })),
    ).rejects.toThrow("REDIRECT:/rate?status=thanks");

    expect(mocks.from).toHaveBeenCalledWith("ai_ratings");
    expect(mocks.upsert).toHaveBeenCalledWith(
      {
        delivery_id: DELIVERY,
        score,
        rated_at: expect.any(String),
      },
      { onConflict: "delivery_id" },
    );
  });

  it.each(["0", "4", "2.5", "NaN"])(
    "rejects out-of-range rating score %s without a write",
    async (score) => {
      await expect(
        recordRatingAction(form({ delivery: DELIVERY, score })),
      ).rejects.toThrow("REDIRECT:/rate?status=invalid");
      expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
      expect(mocks.upsert).not.toHaveBeenCalled();
    },
  );

  it("keeps an unknown rating delivery private when its upsert fails", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    mocks.upsert.mockResolvedValue({
      error: { message: `foreign key leaked ${DELIVERY}` },
    });

    await expect(
      recordRatingAction(form({ delivery: DELIVERY, score: "3" })),
    ).rejects.toThrow("REDIRECT:/rate?status=thanks");

    expect(consoleError).toHaveBeenCalledWith("[rate] upsert failed");
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain(DELIVERY);
    consoleError.mockRestore();
  });

  it("keeps RFC 8058 POST intentional and records AIVIZENS unsubscribe time", async () => {
    const response = await oneClickUnsubscribe(
      new Request(
        `https://aivizens.test/api/unsubscribe?token=${TOKEN}&product=ai`,
        { method: "POST" },
      ),
    );

    expect(response.status).toBe(200);
    expect(await response.text()).toBe("OK");
    expect(mocks.update).toHaveBeenCalledWith({
      status: "unsubscribed",
      unsubscribed_at: expect.any(String),
    });
  });
});
