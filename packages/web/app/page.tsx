import Header from "@/components/header";
import Footer from "@/components/footer";
import AiSubscribeForm from "@/components/ai-subscribe-form";
import LatestPostsGrid from "@/components/latest-posts-grid";
import { BrandIcon } from "@/components/brand-icon";

const COMPANIES: { slug: string; name: string }[] = [
  { slug: "bytedance", name: "字节跳动" },
  { slug: "alibaba", name: "阿里巴巴" },
  { slug: "tencent", name: "腾讯" },
  { slug: "deepseek", name: "DeepSeek" },
  { slug: "xiaomi", name: "小米" },
  { slug: "huawei", name: "华为" },
];

const LOGO_HEIGHT = 36;

export default function AiTrendsHome() {
  return (
    <main className="min-h-screen bg-white">
      <Header />

      {/* Hero */}
      <section id="subscribe" className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-indigo-50 via-white to-white" aria-hidden="true" />
        <div className="relative max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
          <h1 className="text-4xl sm:text-6xl font-bold tracking-tight text-gray-900 mb-6 leading-tight">
            每日 <span className="text-indigo-600">5 分钟</span>，
            <br className="sm:hidden" />
            学会 AI
          </h1>
          <p className="text-lg sm:text-xl text-gray-600 leading-relaxed max-w-2xl mx-auto mb-10">
            获取最新 AI 资讯，了解为什么重要，学习如何应用到工作中。
          </p>

          <AiSubscribeForm variant="hero" />

          {/* Trust bar */}
          <div className="mt-16">
            <p className="text-sm text-gray-500 mb-4">
              已有 <span className="font-semibold text-gray-900">100,000+</span> 读者，来自这些公司：
            </p>
            <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-6 opacity-80 grayscale hover:grayscale-0 hover:opacity-100 transition-all duration-500">
              {COMPANIES.map((c) => (
                <div
                  key={c.slug}
                  className="flex items-center justify-center"
                  style={{ height: LOGO_HEIGHT }}
                  title={c.name}
                >
                  <BrandIcon slug={c.slug} size={LOGO_HEIGHT} title={c.name} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <LatestPostsGrid />

      <Footer />
    </main>
  );
}
