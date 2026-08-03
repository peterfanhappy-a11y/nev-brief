"use client";

import { useRef, useState, type FormEvent } from "react";
import {
  Turnstile,
  type TurnstileInstance,
} from "@marsidev/react-turnstile";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function AiSubscribeForm({
  variant = "hero",
  subscriptionsEnabled,
}: {
  variant?: "hero" | "block";
  subscriptionsEnabled: boolean;
}) {
  const turnstileRef = useRef<TurnstileInstance | null>(null);
  const [email, setEmail] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const [status, setStatus] = useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";

  if (!subscriptionsEnabled) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-center text-sm text-gray-600">
        订阅暂未开放
      </div>
    );
  }

  if (!siteKey) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-center text-sm text-amber-800">
        订阅验证暂不可用
      </div>
    );
  }

  function resetTurnstile() {
    setTurnstileToken("");
    turnstileRef.current?.reset();
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (status === "submitting") return;
    if (!email) {
      setErrorMsg("请填写邮箱");
      setStatus("error");
      return;
    }
    if (!turnstileToken) {
      setErrorMsg("请完成机器人验证");
      setStatus("error");
      return;
    }

    setStatus("submitting");
    setErrorMsg("");
    try {
      const response = await fetch("/api/ai/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, turnstileToken }),
      });
      const data = await response.json().catch(() => ({}));
      if (response.status !== 202) {
        setErrorMsg(data.error ?? "提交失败，请稍后重试");
        setStatus("error");
        resetTurnstile();
        return;
      }
      setStatus("success");
    } catch {
      setErrorMsg("网络错误，请重试");
      setStatus("error");
      resetTurnstile();
    }
  }

  if (status === "success") {
    return (
      <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-6 text-center">
        <h3 className="mb-2 text-xl font-bold text-indigo-700">
          请查收确认邮件
        </h3>
        <p className="text-sm text-gray-700">
          点击邮件中的确认链接后，订阅才会生效。
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className={variant === "hero" ? "w-full max-w-xl mx-auto" : "w-full"}
    >
      <div className="flex flex-col sm:flex-row gap-3">
        <Input
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="输入你的邮箱"
          className="flex-1 h-12 text-base"
        />
        <Button
          type="submit"
          disabled={status === "submitting"}
          className="h-12 px-6 text-base bg-gray-900 hover:bg-gray-800"
        >
          {status === "submitting" ? "提交中…" : "免费订阅"}
        </Button>
      </div>

      <div className="mt-4 flex justify-center">
        <Turnstile
          ref={turnstileRef}
          siteKey={siteKey}
          onSuccess={setTurnstileToken}
          onExpire={() => setTurnstileToken("")}
          onError={() => setTurnstileToken("")}
        />
      </div>

      {status === "error" && (
        <div className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-center text-sm text-red-600">
          {errorMsg}
        </div>
      )}

      <p className="mt-3 text-xs text-gray-500 text-center">
        免费 · 一键退订 · 我们尊重你的隐私
      </p>
    </form>
  );
}
