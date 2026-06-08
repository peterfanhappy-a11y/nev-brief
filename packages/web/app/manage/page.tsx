import Link from "next/link";
import { getSupabaseAdmin } from "@/lib/supabase";
import ManageForm from "@/components/manage-form";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type SearchParams = Promise<{ token?: string }>;

function ErrorCard({ title, msg }: { title: string; msg: string }) {
  return (
    <main className="min-h-screen flex items-center justify-center px-6 py-12">
      <div className="max-w-md w-full bg-white rounded-lg shadow-sm border border-gray-100 p-8">
        <h1 className="text-xl font-semibold mb-2">{title}</h1>
        <p className="text-gray-600 text-sm">{msg}</p>
        <Link href="/" className="text-nev-blue text-sm mt-4 inline-block">
          ← 返回首页
        </Link>
      </div>
    </main>
  );
}

export default async function ManagePage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const { token } = await searchParams;
  if (!token || !UUID_RE.test(token)) {
    return <ErrorCard title="链接无效" msg="管理链接格式不正确或已过期。" />;
  }

  const sb = getSupabaseAdmin();
  const { data: sub } = await sb
    .from("subscribers")
    .select("id, email, status, push_time")
    .eq("unsubscribe_token", token)
    .maybeSingle();

  if (!sub) {
    return <ErrorCard title="链接已失效" msg="未找到对应的订阅记录。" />;
  }

  const { data: prefs } = await sb
    .from("subscriber_preferences")
    .select("brands, topics")
    .eq("subscriber_id", sub.id)
    .maybeSingle();

  // push_time comes back as "HH:MM:SS" from Postgres time; trim to HH:MM for the select
  const pushTime =
    typeof sub.push_time === "string" ? sub.push_time.slice(0, 5) : "08:00";

  return (
    <main className="min-h-screen py-12 px-6">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">订阅管理</h1>
          <p className="text-sm text-gray-600 mt-1">
            <span className="font-mono">{sub.email}</span> ·{" "}
            <span className="text-xs px-2 py-0.5 rounded bg-gray-100">
              {sub.status === "active" ? "✅ 已订阅" :
                sub.status === "paused" ? "⏸ 已暂停" : "❌ 已退订"}
            </span>
          </p>
        </div>

        <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-6 mb-6">
          <ManageForm
            token={token}
            initialBrands={prefs?.brands ?? []}
            initialTopics={prefs?.topics ?? []}
            initialPushTime={pushTime}
          />
        </div>

        <div className="flex justify-between text-sm">
          <Link href={`/unsubscribe?token=${token}`} className="text-red-600">
            退订 NEV 早报
          </Link>
          <Link href="/" className="text-gray-500">
            返回首页
          </Link>
        </div>
      </div>
    </main>
  );
}
