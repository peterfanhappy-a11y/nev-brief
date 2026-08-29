import Link from "next/link";
import { Button } from "@/components/ui/button";
import { recordRatingAction } from "./actions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type SearchParams = Promise<{
  delivery?: string;
  score?: string;
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

export default async function RatePage({ searchParams }: { searchParams: SearchParams }) {
  const { delivery = "", score = "", status } = await searchParams;

  if (status === "thanks") {
    return (
      <Card>
        <div className="text-4xl mb-4">🙌</div>
        <h1 className="text-xl font-semibold mb-2">感谢你的反馈！</h1>
        <Link href="/" className="text-indigo-600 text-sm">返回 AIVIZENS</Link>
      </Card>
    );
  }

  const numericScore = Number(score);
  if (
    status === "invalid" ||
    !UUID_RE.test(delivery) ||
    !Number.isInteger(numericScore) ||
    ![1, 2, 3].includes(numericScore)
  ) {
    return (
      <Card>
        <h1 className="text-xl font-semibold mb-2">评分链接无效</h1>
        <Link href="/" className="text-indigo-600 text-sm">返回 AIVIZENS</Link>
      </Card>
    );
  }

  return (
    <Card>
      <div className="text-4xl mb-4">🙌</div>
      <h1 className="text-xl font-semibold mb-2">提交本期评分？</h1>
      <p className="text-gray-600 text-sm mb-6">点击后记录你的反馈。</p>
      <form action={recordRatingAction}>
        <input type="hidden" name="delivery" value={delivery} />
        <input type="hidden" name="score" value={String(numericScore)} />
        <Button type="submit" className="w-full">提交评分</Button>
      </form>
    </Card>
  );
}
