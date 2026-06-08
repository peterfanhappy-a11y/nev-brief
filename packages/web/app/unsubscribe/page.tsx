import Link from "next/link";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { getSupabaseAdmin } from "@/lib/supabase";
import { Button } from "@/components/ui/button";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type SearchParams = Promise<{ token?: string }>;

async function resubscribeAction(formData: FormData) {
  "use server";
  const token = String(formData.get("token") ?? "");
  if (!UUID_RE.test(token)) return;
  const sb = getSupabaseAdmin();
  await sb
    .from("subscribers")
    .update({ status: "active" })
    .eq("unsubscribe_token", token);
  revalidatePath("/unsubscribe");
  redirect(`/unsubscribe?token=${token}`);
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen flex items-center justify-center px-6 py-12">
      <div className="max-w-md w-full bg-white rounded-lg shadow-sm border border-gray-100 p-8">
        {children}
      </div>
    </main>
  );
}

export default async function UnsubscribePage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const { token } = await searchParams;
  if (!token || !UUID_RE.test(token)) {
    return (
      <Card>
        <h1 className="text-xl font-semibold mb-2">链接无效</h1>
        <p className="text-gray-600 text-sm">退订链接格式不正确或已过期。</p>
        <Link href="/" className="text-nev-blue text-sm mt-4 inline-block">
          ← 返回首页
        </Link>
      </Card>
    );
  }

  const sb = getSupabaseAdmin();
  const { data } = await sb
    .from("subscribers")
    .select("email, status")
    .eq("unsubscribe_token", token)
    .maybeSingle();

  if (!data) {
    return (
      <Card>
        <h1 className="text-xl font-semibold mb-2">链接已失效</h1>
        <p className="text-gray-600 text-sm">未找到对应的订阅记录。</p>
        <Link href="/" className="text-nev-blue text-sm mt-4 inline-block">
          ← 返回首页
        </Link>
      </Card>
    );
  }

  // GET visits auto-unsubscribe — matches the one-click expectation of mail
  // providers and avoids a second confirmation step the user wouldn't expect.
  if (data.status === "active") {
    await sb
      .from("subscribers")
      .update({ status: "unsubscribed" })
      .eq("unsubscribe_token", token);
    data.status = "unsubscribed";
  }

  const unsubscribed = data.status === "unsubscribed";

  return (
    <Card>
      <div className="text-4xl mb-4">{unsubscribed ? "👋" : "✅"}</div>
      <h1 className="text-2xl font-semibold mb-2">
        {unsubscribed ? "已退订 NEV 早报" : "您已是订阅状态"}
      </h1>
      <p className="text-gray-600 text-sm mb-6">
        {unsubscribed ? (
          <>
            <span className="font-mono text-gray-800">{data.email}</span>{" "}
            后续将不会再收到 NEV 早报。如果是误操作，可随时重新订阅。
          </>
        ) : (
          <>
            <span className="font-mono text-gray-800">{data.email}</span>{" "}
            的订阅当前为 <b>{data.status}</b> 状态。
          </>
        )}
      </p>

      {unsubscribed && (
        <form action={resubscribeAction}>
          <input type="hidden" name="token" value={token} />
          <Button type="submit" className="w-full">
            重新订阅
          </Button>
        </form>
      )}

      <div className="mt-6 pt-6 border-t border-gray-100 flex justify-between text-sm">
        <Link href={`/manage?token=${token}`} className="text-nev-blue">
          管理订阅偏好
        </Link>
        <Link href="/" className="text-gray-500">
          返回首页
        </Link>
      </div>
    </Card>
  );
}
