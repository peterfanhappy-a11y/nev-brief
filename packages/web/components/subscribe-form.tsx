"use client";

import { useState } from "react";
import { Turnstile } from "@marsidev/react-turnstile";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";

const TOPICS = [
  { value: "new_car", label: "新车" },
  { value: "sales", label: "销量" },
  { value: "policy", label: "政策" },
  { value: "tech", label: "技术" },
  { value: "overseas", label: "海外" },
  { value: "people", label: "人事" },
  { value: "finance", label: "财务" },
  { value: "recall", label: "召回" },
  { value: "supply_chain", label: "供应链" },
] as const;

const HOT_BRANDS = [
  "BYD",
  "Tesla",
  "NIO",
  "XPeng",
  "Li Auto",
  "AITO",
  "Xiaomi",
] as const;

const SITE_KEY =
  process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "1x00000000000000000000AA";

export default function SubscribeForm() {
  const [email, setEmail] = useState("");
  const [brands, setBrands] = useState<string[]>([...HOT_BRANDS]);
  const [topics, setTopics] = useState<string[]>(["new_car", "sales"]);
  const [pushTime, setPushTime] = useState("08:00");
  const [turnstileToken, setTurnstileToken] = useState<string>("");
  const [status, setStatus] = useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const toggleArray = (arr: string[], val: string) =>
    arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
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
      const res = await fetch("/api/nev/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          brands,
          topics,
          push_time: pushTime,
          turnstile_token: turnstileToken,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErrorMsg(data.error ?? "提交失败");
        setStatus("error");
        return;
      }
      setStatus("success");
    } catch (err) {
      setErrorMsg("网络错误，请重试");
      setStatus("error");
    }
  }

  if (status === "success") {
    return (
      <div className="bg-nev-green/10 border border-nev-green/30 rounded-lg p-6 text-center">
        <h3 className="text-xl font-bold text-nev-green mb-2">✅ 订阅成功</h3>
        <p className="text-gray-700">
          明天早上 8:00 你会收到第一封早报。已发送欢迎邮件，请检查收件箱。
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="email">邮箱 *</Label>
        <Input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
        />
      </div>

      <div className="space-y-2">
        <Label>关注车企（默认热门 7 家）</Label>
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {HOT_BRANDS.map((b) => (
            <label key={b} className="flex items-center gap-2 cursor-pointer">
              <Checkbox
                checked={brands.includes(b)}
                onChange={() => setBrands(toggleArray(brands, b))}
              />
              <span className="text-sm">{b}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <Label>关注主题</Label>
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
          {TOPICS.map((t) => (
            <label
              key={t.value}
              className="flex items-center gap-2 cursor-pointer"
            >
              <Checkbox
                checked={topics.includes(t.value)}
                onChange={() => setTopics(toggleArray(topics, t.value))}
              />
              <span className="text-sm">{t.label}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="push_time">推送时间</Label>
        <select
          id="push_time"
          value={pushTime}
          onChange={(e) => setPushTime(e.target.value)}
          className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-nev-blue focus:ring-offset-2"
        >
          <option value="07:30">07:30</option>
          <option value="08:00">08:00（默认）</option>
          <option value="09:00">09:00</option>
        </select>
      </div>

      <Turnstile siteKey={SITE_KEY} onSuccess={setTurnstileToken} />

      {status === "error" && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3">
          {errorMsg}
        </div>
      )}

      <Button
        type="submit"
        disabled={status === "submitting"}
        className="w-full"
      >
        {status === "submitting" ? "提交中…" : "免费订阅"}
      </Button>

      <p className="text-xs text-gray-500 text-center">
        我们尊重你的隐私 · 邮件中含一键退订链接 · 不会被用于其他用途
      </p>
    </form>
  );
}
