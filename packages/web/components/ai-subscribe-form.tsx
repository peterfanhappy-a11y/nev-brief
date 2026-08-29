"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const HOLD_DURATION_MS = 5_000;

export default function AiSubscribeForm({
  variant = "hero",
  subscriptionsEnabled,
}: {
  variant?: "hero" | "block";
  subscriptionsEnabled: boolean;
}) {
  const holdTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [isHolding, setIsHolding] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => () => {
    if (holdTimeout.current) clearTimeout(holdTimeout.current);
  }, []);

  if (!subscriptionsEnabled) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-center text-sm text-gray-600">
        订阅暂未开放
      </div>
    );
  }

  function cancelHold() {
    if (holdTimeout.current) clearTimeout(holdTimeout.current);
    holdTimeout.current = null;
    setIsHolding(false);
  }

  async function submitSubscription() {
    if (status === "submitting") return;
    setStatus("submitting");
    setErrorMsg("");
    try {
      const response = await fetch("/api/ai/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await response.json().catch(() => ({}));
      if (response.status !== 202) {
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

  function startHold() {
    if (status === "submitting" || isHolding) return;
    if (!email) {
      setErrorMsg("请填写邮箱");
      setStatus("error");
      return;
    }

    setErrorMsg("");
    setIsHolding(true);
    holdTimeout.current = setTimeout(() => {
      holdTimeout.current = null;
      setIsHolding(false);
      void submitSubscription();
    }, HOLD_DURATION_MS);
  }

  function preventSubmit(event: FormEvent) {
    event.preventDefault();
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
      onSubmit={preventSubmit}
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
          type="button"
          disabled={status === "submitting"}
          className="h-12 px-6 text-base bg-gray-900 hover:bg-gray-800"
          onPointerDown={(event) => {
            event.preventDefault();
            startHold();
          }}
          onPointerUp={cancelHold}
          onPointerLeave={cancelHold}
          onPointerCancel={cancelHold}
          onKeyDown={(event) => {
            if (event.key !== " " && event.key !== "Enter") return;
            event.preventDefault();
            startHold();
          }}
          onKeyUp={(event) => {
            if (event.key === " " || event.key === "Enter") cancelHold();
          }}
        >
          {status === "submitting"
            ? "提交中…"
            : isHolding
              ? "继续按住…"
              : "按住 5 秒免费订阅"}
        </Button>
      </div>

      {status === "error" && (
        <div className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-center text-sm text-red-600">
          {errorMsg}
        </div>
      )}

      <p className="mt-3 text-xs text-gray-500 text-center">
        按住 5 秒完成订阅 · 免费 · 一键退订 · 我们尊重你的隐私
      </p>
    </form>
  );
}
