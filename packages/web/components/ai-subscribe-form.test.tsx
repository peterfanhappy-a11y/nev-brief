import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const resetTurnstile = vi.hoisted(() => vi.fn());

vi.mock("@marsidev/react-turnstile", async () => {
  const React = await import("react");
  return {
    Turnstile: React.forwardRef(function MockTurnstile(
      props: {
        siteKey: string;
        onSuccess?: (token: string) => void;
        onExpire?: () => void;
        onError?: () => void;
      },
      ref: React.ForwardedRef<{ reset: () => void }>,
    ) {
      React.useImperativeHandle(ref, () => ({ reset: resetTurnstile }));
      return (
        <div>
          <button
            type="button"
            data-testid="turnstile"
            data-site-key={props.siteKey}
            onClick={() => props.onSuccess?.("verified-turnstile-token")}
          >
            complete verification
          </button>
          <button type="button" onClick={() => props.onExpire?.()}>
            expire verification
          </button>
          <button type="button" onClick={() => props.onError?.()}>
            error verification
          </button>
        </div>
      );
    }),
  };
});

import AiSubscribeForm from "./ai-subscribe-form";

describe("AI subscription form", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_TURNSTILE_SITE_KEY", "test-site-key");
    vi.stubGlobal("React", React);
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders a disabled notice without a form or Turnstile", () => {
    render(<AiSubscribeForm subscriptionsEnabled={false} />);

    expect(screen.getByText("订阅暂未开放")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByTestId("turnstile")).not.toBeInTheDocument();
  });

  it("requires a Turnstile token before sending the request", async () => {
    render(<AiSubscribeForm subscriptionsEnabled />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));

    expect(await screen.findByText("请完成机器人验证")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("sends the official widget token and shows confirmation guidance only for HTTP 202", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true, message: "check_email" }), {
        status: 202,
        headers: { "content-type": "application/json" },
      }),
    );
    render(<AiSubscribeForm subscriptionsEnabled />);

    expect(screen.getByTestId("turnstile")).toHaveAttribute(
      "data-site-key",
      "test-site-key",
    );
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByTestId("turnstile"));
    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));

    expect(await screen.findByText("请查收确认邮件")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/ai/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "reader@example.com",
        turnstileToken: "verified-turnstile-token",
      }),
    });
  });

  it("does not claim success for a non-202 response and resets Turnstile", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    render(<AiSubscribeForm subscriptionsEnabled />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByTestId("turnstile"));
    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));

    await waitFor(() => expect(resetTurnstile).toHaveBeenCalledOnce());
    expect(screen.queryByText("请查收确认邮件")).not.toBeInTheDocument();
    expect(screen.getByText("提交失败，请稍后重试")).toBeInTheDocument();
  });

  it("resets Turnstile after an API failure so the user can retry", async () => {
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
    fireEvent.click(screen.getByTestId("turnstile"));
    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));

    expect(await screen.findByText("rate_limited")).toBeInTheDocument();
    expect(resetTurnstile).toHaveBeenCalledOnce();
  });

  it.each(["expire", "error"])(
    "clears an issued token after Turnstile %s and requires verification again",
    async (event) => {
      render(<AiSubscribeForm subscriptionsEnabled />);
      fireEvent.change(screen.getByRole("textbox"), {
        target: { value: "reader@example.com" },
      });
      fireEvent.click(screen.getByTestId("turnstile"));
      fireEvent.click(
        screen.getByRole("button", { name: `${event} verification` }),
      );
      fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));

      expect(await screen.findByText("请完成机器人验证")).toBeInTheDocument();
      expect(fetch).not.toHaveBeenCalled();
    },
  );

  it("contains no hold-to-verify control or security claim", () => {
    render(<AiSubscribeForm subscriptionsEnabled />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "免费订阅" }));
    expect(screen.queryByText(/长按|按住/)).not.toBeInTheDocument();
  });
});
