import Link from "next/link";
import { Button } from "@/components/ui/button";
import { confirmSubscriptionAction } from "./actions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type SearchParams = Promise<{ token?: string; status?: string }>;

function Card({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen flex items-center justify-center px-6 py-12">
      <div className="max-w-md w-full bg-white rounded-lg shadow-sm border border-gray-100 p-8 text-center">
        {children}
      </div>
    </main>
  );
}

export default async function ConfirmPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const { token = "", status } = await searchParams;

  if (status === "confirmed") {
    return (
      <Card>
        <div className="text-4xl mb-4">✅</div>
        <h1 className="text-2xl font-semibold mb-2">订阅确认成功</h1>
        <p className="text-gray-600 text-sm mb-6">欢迎加入 AIVIZENS · AI 趋势。</p>
        <Link href="/" className="text-indigo-600 text-sm">返回 AIVIZENS</Link>
      </Card>
    );
  }

  if (status === "invalid" || !token) {
    return (
      <Card>
        <h1 className="text-xl font-semibold mb-2">确认链接无效或已过期</h1>
        <p className="text-gray-600 text-sm mb-6">请重新提交订阅申请以获取新链接。</p>
        <Link href="/" className="text-indigo-600 text-sm">返回 AIVIZENS</Link>
      </Card>
    );
  }

  if (status === "error") {
    return (
      <Card>
        <h1 className="text-xl font-semibold mb-2">暂时无法确认</h1>
        <p className="text-gray-600 text-sm mb-6">请稍后重试此确认链接。</p>
        <Link href="/" className="text-indigo-600 text-sm">返回 AIVIZENS</Link>
      </Card>
    );
  }

  return (
    <Card>
      <div className="text-4xl mb-4">✉️</div>
      <h1 className="text-2xl font-semibold mb-2">确认订阅</h1>
      <p className="text-gray-600 text-sm mb-6">
        点击按钮确认订阅 AIVIZENS · AI 趋势。
      </p>
      <form action={confirmSubscriptionAction}>
        <input type="hidden" name="token" value={token} />
        <Button type="submit" className="w-full">确认订阅</Button>
      </form>
    </Card>
  );
}
