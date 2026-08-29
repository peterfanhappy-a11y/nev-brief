"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const HOLD_DURATION_MS = 2_000;

export default function AiSubscribeForm({
  variant = "hero",
  subscriptionsEnabled,
}: {
  variant?: "hero" | "block";
  subscriptionsEnabled: boolean;
}) {
  const holdTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const progressInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const holdStartedAt = useRef(0);
  const isHoldingRef = useRef(false);
  const isSubmittingRef = useRef(false);
  const subscribeButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const progressButtonRef = useRef<HTMLButtonElement>(null);
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [verificationOpen, setVerificationOpen] = useState(false);
  const [isHolding, setIsHolding] = useState(false);
  const [progress, setProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");

  const cancelHold = useCallback((resetProgress = true) => {
    if (holdTimeout.current) clearTimeout(holdTimeout.current);
    if (progressInterval.current) clearInterval(progressInterval.current);
    holdTimeout.current = null;
    progressInterval.current = null;
    isHoldingRef.current = false;
    setIsHolding(false);
    if (resetProgress) setProgress(0);
  }, []);

  const closeVerification = useCallback(() => {
    cancelHold();
    setVerificationOpen(false);
    subscribeButtonRef.current?.focus();
  }, [cancelHold]);

  useEffect(() => () => cancelHold(false), [cancelHold]);

  useEffect(() => {
    if (!verificationOpen) return;

    closeButtonRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeVerification();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [verificationOpen, closeVerification]);

  if (!subscriptionsEnabled) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-center text-sm text-gray-600">
        订阅暂未开放
      </div>
    );
  }

  async function submitSubscription() {
    if (isSubmittingRef.current) return;
    isSubmittingRef.current = true;
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
        isSubmittingRef.current = false;
        return;
      }
      setStatus("success");
    } catch {
      setErrorMsg("网络错误，请重试");
      setStatus("error");
      isSubmittingRef.current = false;
    }
  }

  function openVerification() {
    if (isSubmittingRef.current) return;
    if (!email) {
      setErrorMsg("请填写邮箱");
      setStatus("error");
      return;
    }

    setErrorMsg("");
    setVerificationOpen(true);
    setProgress(0);
  }

  function startHold() {
    if (isSubmittingRef.current || isHoldingRef.current) return;

    isHoldingRef.current = true;
    setIsHolding(true);
    holdStartedAt.current = Date.now();
    progressInterval.current = setInterval(() => {
      setProgress(
        Math.min(
          Math.round(((Date.now() - holdStartedAt.current) / HOLD_DURATION_MS) * 100),
          99,
        ),
      );
    }, 50);
    holdTimeout.current = setTimeout(() => {
      cancelHold(false);
      setProgress(100);
      setVerificationOpen(false);
      void submitSubscription();
    }, HOLD_DURATION_MS);
  }

  function trapFocus(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab") return;

    const closeButton = closeButtonRef.current;
    const progressButton = progressButtonRef.current;
    if (!closeButton || !progressButton) return;

    event.preventDefault();
    if (event.shiftKey) {
      (document.activeElement === closeButton ? progressButton : closeButton).focus();
    } else {
      (document.activeElement === progressButton ? closeButton : progressButton).focus();
    }
  }

  function preventSubmit(event: FormEvent) {
    event.preventDefault();
  }

  if (status === "success") {
    return (
      <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-6 text-center">
        <h3 className="mb-2 text-xl font-bold text-indigo-700">
          订阅请求已收到
        </h3>
        <p className="text-sm text-gray-700">
          如需确认，我们会向你的邮箱发送确认链接。若几分钟内未收到，请检查垃圾邮件或稍后重试。
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
          ref={subscribeButtonRef}
          type="button"
          disabled={status === "submitting"}
          className="h-12 px-6 text-base bg-gray-900 hover:bg-gray-800"
          onClick={openVerification}
        >
          {status === "submitting" ? "正在提交…" : "免费订阅"}
        </Button>
      </div>

      {verificationOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="人机验证"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm sm:px-6"
          onKeyDown={trapFocus}
          onClick={(event) => {
            if (event.target === event.currentTarget) closeVerification();
          }}
        >
          <div className="relative w-full max-w-md overflow-hidden rounded-3xl border border-indigo-100 bg-white p-6 text-center shadow-2xl shadow-indigo-950/30 sm:p-8">
            <div
              aria-hidden="true"
              className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-400"
            />
            <button
              ref={closeButtonRef}
              type="button"
              aria-label="关闭验证"
              className="absolute right-4 top-4 h-9 w-9 rounded-full text-gray-500 transition-colors hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
              onClick={closeVerification}
            >
              ×
            </button>
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-lg text-indigo-600" aria-hidden="true">
              ✦
            </div>
            <p className="mt-4 text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">
              安全验证 · 约 2 秒
            </p>
            <h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">确认是你本人</h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">
              请长按进度条 2 秒进行人机验证。
            </p>

            <button
              ref={progressButtonRef}
              type="button"
              aria-label="长按进度条 2 秒"
              className="relative mt-7 h-14 w-full touch-none select-none overflow-hidden rounded-2xl border border-indigo-100 bg-slate-100 text-sm font-semibold text-slate-700 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
              style={{
                touchAction: "none",
                userSelect: "none",
                WebkitUserSelect: "none",
                WebkitTouchCallout: "none",
              }}
              onPointerDown={(event) => {
                event.preventDefault();
                if (event.button > 0) return;
                try {
                  event.currentTarget.setPointerCapture(event.pointerId);
                } catch {
                  // Older mobile browsers may not expose pointer capture.
                }
                startHold();
              }}
              onPointerUp={() => cancelHold()}
              onPointerLeave={() => cancelHold()}
              onPointerCancel={() => cancelHold()}
              onContextMenu={(event) => event.preventDefault()}
              onDragStart={(event) => event.preventDefault()}
              onKeyDown={(event) => {
                if (event.key !== " " && event.key !== "Enter") return;
                event.preventDefault();
                startHold();
              }}
              onKeyUp={(event) => {
                if (event.key === " " || event.key === "Enter") cancelHold();
              }}
            >
              <span
                role="progressbar"
                aria-label="验证进度"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
                className="absolute inset-y-0 left-0 bg-gradient-to-r from-indigo-600 via-violet-600 to-cyan-500 transition-[width]"
                style={{ width: `${progress}%` }}
              />
              <span className="relative inline-flex items-center gap-2">
                <span aria-hidden="true">{isHolding ? "✦" : "●"}</span>
                {isHolding ? `验证中 ${progress}%` : "按住开始验证"}
              </span>
            </button>
            <p className="mt-4 text-xs text-slate-400">无需验证码，不会收集额外信息</p>
          </div>
        </div>
      )}

      {status === "error" && (
        <div className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-center text-sm text-red-600">
          {errorMsg}
        </div>
      )}

      <p className="mt-3 text-xs text-gray-500 text-center">
        免费 · 邮箱确认 · 一键退订 · 我们尊重你的隐私
      </p>
    </form>
  );
}
