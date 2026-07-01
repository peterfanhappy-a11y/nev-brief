"use client";

import { useState } from "react";
import { Turnstile } from "@marsidev/react-turnstile";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const SITE_KEY =
  process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "1x00000000000000000000AA";

export default function AiSubscribeForm({
  variant = "hero",
}: {
  variant?: "hero" | "block";
}) {
  const [email, setEmail] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const [status, setStatus] = useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (status === "submitting") return;
    if (!email) {
      setErrorMsg("请填写邮箱");
      setStatus("error");
      return;
    }
    if (!turnstileToken) {
      setErrorMsg("请完成人机验证");
      setStatus("error");
      return;
    }
    setStatus("submitting");
    setErrorMsg("");
    try {
      const res = await fetch("/api/ai/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, turnstile_token: turnstileToken }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErrorMsg(data.error ?? "提交失败，请稍后重试");
        setStatus("error");
        return;
      }
      setStatus("success");
    } catch {
      setErrorMsg("网络错误，请重试");
      setStatus("error");
    }
  }

  if (status === "success") {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-5 text-center">
        <div className="text-lg font-semibold text-emerald-700 mb-1">
          ✅ 订阅成功
        </div>
        <p className="text-sm text-emerald-800">
          欢迎邮件已发送到 <span className="font-mono">{email}</span>，请检查收件箱。
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className={
        variant === "hero"
          ? "w-full max-w-xl mx-auto"
          : "w-full"
      }
    >
      <div className="flex flex-col sm:flex-row gap-3">
        <Input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
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
        <Turnstile siteKey={SITE_KEY} onSuccess={setTurnstileToken} />
      </div>

      {status === "error" && (
        <div className="mt-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3 text-center">
          {errorMsg}
        </div>
      )}

      <p className="mt-3 text-xs text-gray-500 text-center">
        免费 · 一键退订 · 我们尊重你的隐私
      </p>
    </form>
  );
}
