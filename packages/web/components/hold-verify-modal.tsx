"use client";

import { useEffect, useRef, useState } from "react";

const HOLD_DURATION_MS = 5000;

type Props = {
  open: boolean;
  onClose: () => void;
  onConfirmed: () => void;
};

export default function HoldVerifyModal({ open, onClose, onConfirmed }: Props) {
  const [progress, setProgress] = useState(0);
  const [verified, setVerified] = useState(false);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  // Reset every time the modal is (re)opened.
  useEffect(() => {
    if (open) {
      setProgress(0);
      setVerified(false);
      startRef.current = null;
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    }
  }, [open]);

  useEffect(
    () => () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    },
    [],
  );

  const startHold = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (verified) return;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      // Some browsers throw if capture is unsupported; hold still works.
    }
    startRef.current = performance.now();
    const tick = () => {
      const elapsed = performance.now() - (startRef.current ?? 0);
      const pct = Math.min(1, elapsed / HOLD_DURATION_MS);
      setProgress(pct);
      if (pct >= 1) {
        setVerified(true);
        rafRef.current = null;
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  };

  const stopHold = () => {
    if (verified) return;
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    setProgress(0);
    startRef.current = null;
  };

  // Close on ESC
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const percent = Math.round(progress * 100);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        // Click on backdrop closes; click on card doesn't propagate.
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl relative">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 h-8 w-8 rounded-full text-gray-400 hover:bg-gray-100 hover:text-gray-600 flex items-center justify-center"
          aria-label="关闭"
        >
          ✕
        </button>

        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            在我们继续之前…
          </h2>
          <p className="text-sm text-gray-600 leading-relaxed">
            按住以确认您是人类
            <br />
            （而非机器人）。
          </p>
        </div>

        {!verified ? (
          <button
            type="button"
            onPointerDown={startHold}
            onPointerUp={stopHold}
            onPointerLeave={stopHold}
            onPointerCancel={stopHold}
            className="relative w-full h-16 rounded-full bg-gray-100 border border-gray-200 overflow-hidden select-none touch-none focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            aria-label="按住此按钮 5 秒以确认"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            role="progressbar"
          >
            <div
              className="absolute inset-y-0 left-0 bg-indigo-600"
              style={{ width: `${percent}%`, transition: percent === 0 ? "width 0.2s ease-out" : "none" }}
            />
            <div className="relative flex items-center justify-center gap-2 h-full font-medium">
              <span className="text-xl" aria-hidden="true">
                👤
              </span>
              <span className={percent > 45 ? "text-white" : "text-gray-700"}>
                {percent === 0 ? "按住此按钮" : `继续按住 ${percent}%`}
              </span>
            </div>
          </button>
        ) : (
          <button
            type="button"
            onClick={onConfirmed}
            className="w-full h-16 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white text-base font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 transition-colors"
          >
            ✓ 已验证 · 再次按下以完成订阅
          </button>
        )}

        <p className="mt-6 text-xs text-gray-400 text-center leading-relaxed">
          此步骤帮助我们防止自动程序滥用注册。
        </p>
      </div>
    </div>
  );
}
