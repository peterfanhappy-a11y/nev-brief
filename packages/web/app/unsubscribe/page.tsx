import Link from "next/link";
import { Button } from "@/components/ui/button";
import { getSupabaseAdmin } from "@/lib/supabase";
import { requestUnsubscribeAction, unsubscribeAction } from "./actions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type SearchParams = Promise<{
  token?: string;
  product?: string;
  status?: string;
}>;

function Card({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen flex items-center justify-center px-6 py-12">
      <div className="max-w-md w-full bg-white rounded-lg shadow-sm border border-gray-100 p-8 text-center">
        {children}
      </div>
    </main>
  );
}

function ResubscribeLink() {
  return (
    <Link href="/" className="text-indigo-600 text-sm">
      重新订阅
    </Link>
  );
}

export default async function UnsubscribePage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const { token = "", status } = await searchParams;

  if (status === "unsubscribed") {
    return (
      <Card>
        <div className="text-4xl mb-4">👋</div>
        <h1 className="text-2xl font-semibold mb-2">已退订 AIVIZENS · AI 趋势</h1>
        <p className="text-gray-600 text-sm mb-6">后续将不会再收到趋势邮件。</p>
        <ResubscribeLink />
      </Card>
    );
  }

  if (status === "error") {
    return (
      <Card>
        <h1 className="text-xl font-semibold mb-2">暂时无法退订</h1>
        <p className="text-gray-600 text-sm mb-6">请稍后重试此链接。</p>
        <Link href="/" className="text-indigo-600 text-sm">返回 AIVIZENS</Link>
      </Card>
    );
  }

  if (status === "requested") {
    return (
      <Card>
        <h1 className="text-xl font-semibold mb-2">请查收退订邮件</h1>
        <p className="text-gray-600 text-sm mb-6">
          如果该邮箱当前订阅了 AIVIZENS，我们已发送安全退订链接。
        </p>
        <Link href="/" className="text-indigo-600 text-sm">返回 AIVIZENS</Link>
      </Card>
    );
  }

  if (!token) {
    return (
      <Card>
        <h1 className="text-2xl font-semibold mb-2">退订 AIVIZENS</h1>
        <p className="text-gray-600 text-sm mb-6">
          输入订阅邮箱，我们会发送一封安全退订邮件。
        </p>
        <form action={requestUnsubscribeAction} className="space-y-3">
          <label className="block text-left text-sm font-medium text-gray-700" htmlFor="email">
            订阅邮箱
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            className="w-full rounded-md border border-gray-300 px-3 py-2"
          />
          <Button type="submit" className="w-full">发送退订链接</Button>
        </form>
      </Card>
    );
  }

  if (status === "invalid" || !UUID_RE.test(token)) {
    return (
      <Card>
        <h1 className="text-xl font-semibold mb-2">退订链接无效或已过期</h1>
        <Link href="/" className="text-indigo-600 text-sm mt-4 inline-block">
          返回 AIVIZENS
        </Link>
      </Card>
    );
  }

  const { data, error } = await getSupabaseAdmin()
    .from("ai_subscribers")
    .select("status")
    .eq("unsubscribe_token", token)
    .maybeSingle();

  if (error || !data) {
    return (
      <Card>
        <h1 className="text-xl font-semibold mb-2">退订链接无效或已过期</h1>
        <Link href="/" className="text-indigo-600 text-sm mt-4 inline-block">
          返回 AIVIZENS
        </Link>
      </Card>
    );
  }

  if (data.status === "unsubscribed") {
    return (
      <Card>
        <div className="text-4xl mb-4">👋</div>
        <h1 className="text-2xl font-semibold mb-2">已退订 AIVIZENS · AI 趋势</h1>
        <p className="text-gray-600 text-sm mb-6">
          如需恢复邮件，请重新提交订阅并完成邮箱确认。
        </p>
        <ResubscribeLink />
      </Card>
    );
  }

  return (
    <Card>
      <div className="text-4xl mb-4">✉️</div>
      <h1 className="text-2xl font-semibold mb-2">确认退订</h1>
      <p className="text-gray-600 text-sm mb-6">
        点击按钮后将不再收到 AIVIZENS · AI 趋势邮件。
      </p>
      <form action={unsubscribeAction}>
        <input type="hidden" name="token" value={token} />
        <Button type="submit" className="w-full">确认退订</Button>
      </form>
    </Card>
  );
}
