import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AiSubscribeForm from "./ai-subscribe-form";

describe("AI subscription form", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders a disabled notice without a form", () => {
    render(<AiSubscribeForm subscriptionsEnabled={false} />);

    expect(screen.getByText("订阅暂未开放")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("submits only after the reader holds the button for five seconds", async () => {
    vi.useFakeTimers();
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true, message: "check_email" }), {
        status: 202,
        headers: { "content-type": "application/json" },
      }),
    );
    render(<AiSubscribeForm subscriptionsEnabled />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });

    const button = screen.getByRole("button", { name: "按住 5 秒免费订阅" });
    fireEvent.pointerDown(button, { button: 0 });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_999);
    });
    expect(fetch).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    vi.useRealTimers();

    expect(fetch).toHaveBeenCalledWith("/api/ai/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "reader@example.com" }),
    });
    expect(await screen.findByText("请查收确认邮件")).toBeInTheDocument();
  });

  it("cancels a subscription hold when the reader releases early", async () => {
    vi.useFakeTimers();
    render(<AiSubscribeForm subscriptionsEnabled />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });

    const button = screen.getByRole("button", { name: "按住 5 秒免费订阅" });
    fireEvent.pointerDown(button, { button: 0 });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    fireEvent.pointerUp(button);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });

    expect(fetch).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "按住 5 秒免费订阅" })).toBeInTheDocument();
  });

  it("does not render a Cloudflare verification widget", () => {
    render(<AiSubscribeForm subscriptionsEnabled />);

    expect(screen.getByRole("button", { name: "按住 5 秒免费订阅" })).toBeInTheDocument();
    expect(screen.queryByText(/机器人验证|Cloudflare/i)).not.toBeInTheDocument();
  });

  it("shows the API error without presenting a false confirmation", async () => {
    vi.useFakeTimers();
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ error: "rate_limited" }), {
        status: 429,
        headers: { "content-type": "application/json" },
      }),
    );
    render(<AiSubscribeForm subscriptionsEnabled />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });
    fireEvent.pointerDown(
      screen.getByRole("button", { name: "按住 5 秒免费订阅" }),
      { button: 0 },
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    vi.useRealTimers();

    expect(await screen.findByText("rate_limited")).toBeInTheDocument();
    expect(screen.queryByText("请查收确认邮件")).not.toBeInTheDocument();
  });
});
