import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const RAW_TOKEN = "confirmation-token";
const TOKEN_HASH =
  "23a0f8a5d44eb66f9f082c737258aaf003ccf023127f695078f39fd7f57cd2e6";
const UNSUBSCRIBE_TOKEN = "11111111-1111-4111-8111-111111111111";

const mocks = vi.hoisted(() => ({
  getSupabaseAdmin: vi.fn(),
  rpc: vi.fn(),
  sendWelcome: vi.fn(),
  redirect: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  getSupabaseAdmin: mocks.getSupabaseAdmin,
}));
vi.mock("@/lib/ai-welcome-email", () => ({
  sendAiWelcomeEmail: mocks.sendWelcome,
}));
vi.mock("next/navigation", () => ({
  redirect: mocks.redirect,
}));

import { confirmSubscriptionAction } from "./actions";
import ConfirmPage from "./page";

function form(token = RAW_TOKEN): FormData {
  const data = new FormData();
  data.set("token", token);
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

describe("confirmation page", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    mocks.getSupabaseAdmin.mockReturnValue({ rpc: mocks.rpc });
    mocks.rpc.mockResolvedValue({
      data: [
        {
          id: "22222222-2222-4222-8222-222222222222",
          email: "reader@example.com",
          unsubscribe_token: UNSUBSCRIBE_TOKEN,
        },
      ],
      error: null,
    });
    mocks.sendWelcome.mockResolvedValue(undefined);
    mocks.redirect.mockImplementation((url: string) => {
      throw new Error(`REDIRECT:${url}`);
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders a confirmation form without touching the database", async () => {
    renderServerActionPage(
      await ConfirmPage({
        searchParams: Promise.resolve({ token: RAW_TOKEN }),
      }),
    );

    expect(screen.getByRole("button", { name: "确认订阅" })).toBeInTheDocument();
    expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
    expect(mocks.rpc).not.toHaveBeenCalled();
    expect(mocks.sendWelcome).not.toHaveBeenCalled();
  });

  it("atomically confirms a token hash once, then sends the welcome email", async () => {
    await expect(confirmSubscriptionAction(form())).rejects.toThrow(
      "REDIRECT:/confirm?status=confirmed",
    );

    expect(mocks.rpc).toHaveBeenCalledOnce();
    expect(mocks.rpc).toHaveBeenCalledWith("confirm_ai_subscription", {
      token_hash: TOKEN_HASH,
      now_at: expect.any(String),
    });
    expect(mocks.sendWelcome).toHaveBeenCalledWith(
      "reader@example.com",
      UNSUBSCRIBE_TOKEN,
      TOKEN_HASH,
    );
    expect(JSON.stringify(mocks.rpc.mock.calls)).not.toContain(RAW_TOKEN);
  });

  it.each(["replayed", "expired", "unknown"])(
    "uses the same invalid state and sends no email for a %s token",
    async () => {
      mocks.rpc.mockResolvedValue({ data: [], error: null });

      await expect(confirmSubscriptionAction(form())).rejects.toThrow(
        "REDIRECT:/confirm?status=invalid",
      );

      expect(mocks.rpc).toHaveBeenCalledOnce();
      expect(mocks.sendWelcome).not.toHaveBeenCalled();
    },
  );

  it("keeps a completed confirmation when welcome delivery fails", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    mocks.sendWelcome.mockRejectedValue(
      new Error(`provider leaked reader@example.com ${RAW_TOKEN}`),
    );

    await expect(confirmSubscriptionAction(form())).rejects.toThrow(
      "REDIRECT:/confirm?status=confirmed",
    );

    expect(mocks.rpc).toHaveBeenCalledOnce();
    expect(mocks.sendWelcome).toHaveBeenCalledOnce();
    expect(consoleError).toHaveBeenCalledWith(
      "[confirm] welcome email delivery failed",
    );
    expect(JSON.stringify(consoleError.mock.calls)).not.toMatch(
      /reader@example\.com|confirmation-token/,
    );
    consoleError.mockRestore();
  });

  it("returns one static retry state when the atomic RPC fails", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    mocks.rpc.mockResolvedValue({
      data: null,
      error: { message: `db leaked ${RAW_TOKEN}` },
    });

    await expect(confirmSubscriptionAction(form())).rejects.toThrow(
      "REDIRECT:/confirm?status=error",
    );

    expect(mocks.sendWelcome).not.toHaveBeenCalled();
    expect(consoleError).toHaveBeenCalledWith("[confirm] atomic confirmation failed");
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain(RAW_TOKEN);
    consoleError.mockRestore();
  });
});
