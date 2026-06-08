"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

const TOPICS: { value: string; label: string }[] = [
  { value: "new_car", label: "新车" },
  { value: "sales", label: "销量" },
  { value: "policy", label: "政策" },
  { value: "tech", label: "技术" },
  { value: "overseas", label: "海外" },
  { value: "people", label: "人事" },
  { value: "finance", label: "财务" },
  { value: "recall", label: "召回" },
  { value: "supply_chain", label: "供应链" },
  { value: "battery_tech", label: "电池技术" },
  { value: "autonomous_driving", label: "智能驾驶" },
  { value: "smart_cockpit", label: "智能座舱" },
  { value: "ota_update", label: "OTA" },
  { value: "chassis", label: "底盘" },
  { value: "exterior_design", label: "外观" },
];

const HOT_BRANDS = [
  "BYD", "Tesla", "NIO", "XPeng", "Li Auto", "AITO", "Xiaomi",
  "Leapmotor", "Zeekr", "Geely", "Chery",
];

const PUSH_TIMES = [
  { value: "07:30", label: "07:30" },
  { value: "08:00", label: "08:00（默认）" },
  { value: "09:00", label: "09:00" },
];

export default function ManageForm({
  token,
  initialBrands,
  initialTopics,
  initialPushTime,
}: {
  token: string;
  initialBrands: string[];
  initialTopics: string[];
  initialPushTime: string;
}) {
  const [brands, setBrands] = useState<string[]>(initialBrands);
  const [topics, setTopics] = useState<string[]>(initialTopics);
  const [pushTime, setPushTime] = useState(initialPushTime);
  const [status, setStatus] =
    useState<"idle" | "submitting" | "saved" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const toggle = (arr: string[], v: string) =>
    arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("submitting");
    setErrorMsg("");
    try {
      const res = await fetch("/api/preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, brands, topics, push_time: pushTime }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErrorMsg(data.error ?? "保存失败");
        setStatus("error");
        return;
      }
      setStatus("saved");
    } catch {
      setErrorMsg("网络错误，请重试");
      setStatus("error");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <Label>关注车企</Label>
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {HOT_BRANDS.map((b) => (
            <label key={b} className="flex items-center gap-2 cursor-pointer">
              <Checkbox
                checked={brands.includes(b)}
                onChange={() => setBrands(toggle(brands, b))}
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
                onChange={() => setTopics(toggle(topics, t.value))}
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
          {PUSH_TIMES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {status === "saved" && (
        <div className="text-sm text-nev-green bg-nev-green/10 border border-nev-green/30 rounded p-3">
          ✅ 偏好已保存
        </div>
      )}
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
        {status === "submitting" ? "保存中…" : "保存偏好"}
      </Button>
    </form>
  );
}
