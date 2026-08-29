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

  it("opens a five-second hold verification dialog before subscription", () => {
    render(<AiSubscribeForm subscriptionsEnabled />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });

    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));

    expect(screen.getByRole("dialog", { name: "人机验证" })).toBeInTheDocument();
    expect(screen.getByText("请长按进度条 5 秒进行人机验证。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "长按进度条 5 秒" })).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("closes the verification dialog and returns focus to subscription", () => {
    render(<AiSubscribeForm subscriptionsEnabled />);
    const subscribe = screen.getByRole("button", { name: "免费订阅" });
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });

    fireEvent.click(subscribe);
    expect(screen.getByRole("button", { name: "关闭验证" })).toHaveFocus();

    fireEvent.click(screen.getByRole("button", { name: "关闭验证" }));
    expect(screen.queryByRole("dialog", { name: "人机验证" })).not.toBeInTheDocument();
    expect(subscribe).toHaveFocus();
  });

  it("closes the verification dialog when Escape is pressed", () => {
    render(<AiSubscribeForm subscriptionsEnabled />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: "人机验证" })).not.toBeInTheDocument();
  });

  it("keeps keyboard focus inside the verification dialog", () => {
    render(<AiSubscribeForm subscriptionsEnabled />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));

    const close = screen.getByRole("button", { name: "关闭验证" });
    const progress = screen.getByRole("button", { name: "长按进度条 5 秒" });
    fireEvent.keyDown(close, { key: "Tab" });
    expect(progress).toHaveFocus();
    fireEvent.keyDown(progress, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(close, { key: "Tab", shiftKey: true });
    expect(progress).toHaveFocus();
  });

  it("automatically submits after a five-second verification hold", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));

    const button = screen.getByRole("button", { name: "长按进度条 5 秒" });
    fireEvent.pointerDown(button, { button: 0 });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_999);
    });
    expect(fetch).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    expect(fetch).toHaveBeenCalledWith("/api/ai/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "reader@example.com" }),
    });
    expect(fetch).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
    expect(await screen.findByText("请查收确认邮件")).toBeInTheDocument();
  });

  it("cancels a verification hold when the reader releases early", async () => {
    vi.useFakeTimers();
    render(<AiSubscribeForm subscriptionsEnabled />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));

    const progress = screen.getByRole("button", { name: "长按进度条 5 秒" });
    fireEvent.pointerDown(progress, { button: 0 });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    fireEvent.pointerUp(progress);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });

    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not render a Cloudflare verification widget", () => {
    render(<AiSubscribeForm subscriptionsEnabled />);

    expect(screen.getByRole("button", { name: "免费订阅" })).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));
    fireEvent.pointerDown(screen.getByRole("button", { name: "长按进度条 5 秒" }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    vi.useRealTimers();
    expect(await screen.findByText("rate_limited")).toBeInTheDocument();
    expect(screen.queryByText("请查收确认邮件")).not.toBeInTheDocument();
  });
});
