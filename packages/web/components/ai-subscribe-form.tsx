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

const HOLD_DURATION_MS = 5_000;

export default function AiSubscribeForm({
  variant = "hero",
  subscriptionsEnabled,
}: {
  variant?: "hero" | "block";
  subscriptionsEnabled: boolean;
}) {
  const holdTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const progressInterval = useRef<ReturnType<typeof setInterval> | null>(null);
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
    progressInterval.current = setInterval(() => {
      setProgress((current) => Math.min(current + 1, 99));
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
          ref={subscribeButtonRef}
          type="button"
          disabled={status === "submitting"}
          className="h-12 px-6 text-base bg-gray-900 hover:bg-gray-800"
          onClick={openVerification}
        >
          免费订阅
        </Button>
      </div>

      {verificationOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="人机验证"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-6"
          onKeyDown={trapFocus}
          onClick={(event) => {
            if (event.target === event.currentTarget) closeVerification();
          }}
        >
          <div className="relative w-full max-w-md rounded-xl bg-white p-6 text-center shadow-xl">
            <button
              ref={closeButtonRef}
              type="button"
              aria-label="关闭验证"
              className="absolute right-4 top-4 h-8 w-8 rounded-full text-gray-500 hover:bg-gray-100"
              onClick={closeVerification}
            >
              ×
            </button>
            <h2 className="text-xl font-bold text-gray-900">人机验证</h2>
            <p className="mt-3 text-sm text-gray-600">
              请长按进度条 5 秒进行人机验证。
            </p>

            <button
              ref={progressButtonRef}
              type="button"
              aria-label="长按进度条 5 秒"
              className="relative mt-6 h-12 w-full overflow-hidden rounded-full bg-gray-200 text-sm font-medium text-gray-700"
              onPointerDown={(event) => {
                event.preventDefault();
                if (event.button > 0) return;
                startHold();
              }}
              onPointerUp={() => cancelHold()}
              onPointerLeave={() => cancelHold()}
              onPointerCancel={() => cancelHold()}
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
                className="absolute inset-y-0 left-0 bg-indigo-600 transition-[width]"
                style={{ width: `${progress}%` }}
              />
              <span className="relative">{isHolding ? `验证中 ${progress}%` : "按住开始验证"}</span>
            </button>
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
