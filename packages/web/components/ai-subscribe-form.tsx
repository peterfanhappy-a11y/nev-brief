"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import HoldVerifyModal from "@/components/hold-verify-modal";

export default function AiSubscribeForm({
  variant = "hero",
}: {
  variant?: "hero" | "block";
}) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [status, setStatus] = useState<"idle" | "submitting" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  function handleFormSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (status === "submitting") return;
    if (!email) {
      setErrorMsg("请填写邮箱");
      setStatus("error");
      return;
    }
    setErrorMsg("");
    setStatus("idle");
    setModalOpen(true);
  }

  async function handleVerifiedConfirm() {
    setModalOpen(false);
    setStatus("submitting");
    try {
      const res = await fetch("/api/ai/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErrorMsg(data.error ?? "提交失败，请稍后重试");
        setStatus("error");
        return;
      }
      router.push(
        `/subscribed?product=ai&email=${encodeURIComponent(email)}`,
      );
    } catch {
      setErrorMsg("网络错误，请重试");
      setStatus("error");
    }
  }

  return (
    <>
      <form
        onSubmit={handleFormSubmit}
        className={variant === "hero" ? "w-full max-w-xl mx-auto" : "w-full"}
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

        {status === "error" && (
          <div className="mt-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3 text-center">
            {errorMsg}
          </div>
        )}

        <p className="mt-3 text-xs text-gray-500 text-center">
          免费 · 一键退订 · 我们尊重你的隐私
        </p>
      </form>

      <HoldVerifyModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onConfirmed={handleVerifiedConfirm}
      />
    </>
  );
}
