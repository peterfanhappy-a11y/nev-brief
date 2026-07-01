import Link from "next/link";
import Header from "@/components/header";
import Footer from "@/components/footer";
import { parseProduct, productLabel } from "@/lib/subscribers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type SearchParams = Promise<{ product?: string; email?: string }>;

export default async function SubscribedPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const params = await searchParams;
  const product = parseProduct(params.product);
  const label = productLabel(product);
  const email = (params.email ?? "").trim();

  return (
    <main className="min-h-screen bg-white flex flex-col">
      <Header />

      <section className="flex-1 flex items-center justify-center px-6 py-16">
        <div className="max-w-2xl mx-auto text-center">
          <div className="mx-auto mb-6 inline-flex items-center justify-center w-20 h-20 rounded-full bg-emerald-100 text-emerald-600">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-10 h-10"
              aria-hidden="true"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-4">
            订阅成功
          </h1>
          <p className="text-lg text-gray-700 mb-2">
            欢迎加入 <strong>{label}</strong>！
          </p>
          {email && (
            <p className="text-sm text-gray-500 mb-8">
              欢迎邮件已发送到{" "}
              <span className="font-mono text-gray-800">{email}</span>，请检查收件箱（含垃圾邮件文件夹）。
            </p>
          )}

          <div className="mt-10">
            <Link
              href="/"
              className="inline-flex items-center rounded-md bg-gray-900 px-6 py-3 text-sm font-medium text-white hover:bg-gray-800"
            >
              返回首页
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
