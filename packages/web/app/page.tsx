import SubscribeForm from "@/components/subscribe-form";

export default function HomePage() {
  return (
    <main className="min-h-screen">
      {/* Hero */}
      <section className="bg-gradient-to-b from-nev-blue to-nev-blue/80 text-white py-16">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold mb-4">🚗 NEV 早报</h1>
          <p className="text-xl text-white/90">
            每天早上 8:00 送达 · 10 条新能源汽车行业精选 + 主要车企日销量数据
          </p>
        </div>
      </section>

      {/* Value props */}
      <section className="max-w-5xl mx-auto px-6 py-12 grid sm:grid-cols-3 gap-6">
        {[
          {
            emoji: "📊",
            title: "10 条精选",
            desc: "从 200+ 信源挑出当天最重要 10 条",
          },
          {
            emoji: "🚀",
            title: "日销量数据",
            desc: "CPCA / CAAM 周月报，主要车企最新数据",
          },
          {
            emoji: "🎯",
            title: "行业必读",
            desc: "车企产品 / 战略 / 销售 必备日历表",
          },
        ].map((v) => (
          <div
            key={v.title}
            className="bg-white rounded-lg p-6 shadow-sm border border-gray-100"
          >
            <div className="text-3xl mb-3">{v.emoji}</div>
            <h3 className="text-lg font-semibold mb-2">{v.title}</h3>
            <p className="text-gray-600 text-sm leading-relaxed">{v.desc}</p>
          </div>
        ))}
      </section>

      {/* Sample briefs */}
      <section className="max-w-5xl mx-auto px-6 py-8">
        <h2 className="text-2xl font-bold mb-6">最近的早报样例</h2>
        <div className="space-y-4">
          {SAMPLES.map((s) => (
            <article
              key={s.title}
              className="bg-white rounded-lg p-5 shadow-sm border border-gray-100"
            >
              <h3 className="font-semibold text-nev-blue mb-1">{s.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">
                {s.summary}
              </p>
              <div className="text-xs text-gray-400 mt-2">
                {s.source} · {s.date}
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Subscribe form */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-xl mx-auto px-6">
          <h2 className="text-2xl font-bold text-center mb-2">立刻订阅</h2>
          <p className="text-center text-gray-600 mb-8">
            免费 · 一键退订 · 永远不发广告
          </p>
          <div className="bg-white rounded-lg p-8 shadow-sm border border-gray-100">
            <SubscribeForm />
          </div>
        </div>
      </section>

      <footer className="border-t border-gray-200 py-8 text-center text-sm text-gray-500">
        © 2026 NEV 早报 ·{" "}
        <a href="/about" className="hover:text-nev-blue">
          关于
        </a>{" "}
        ·{" "}
        <a href="/privacy" className="hover:text-nev-blue">
          隐私
        </a>{" "}
        ·{" "}
        <a href="/contact" className="hover:text-nev-blue">
          联系
        </a>
      </footer>
    </main>
  );
}

const SAMPLES = [
  {
    title: "特斯拉 Model Y 焕新版 6 月交付，起售 26.4 万",
    summary:
      "特斯拉中国宣布 Model Y 焕新版于 6 月正式开启交付，标准续航版 26.4 万元起。新车将搭载第三代自动驾驶硬件…",
    source: "路透 / 36氪 / 特斯拉中国官博",
    date: "2026-05-30",
  },
  {
    title: "比亚迪海豹 06 上市，售价 8.98 万起",
    summary:
      "5 月 30 日，比亚迪发布全新海豹 06 EV，售价区间 8.98-13.98 万元。基于 e3.0 平台打造，CLTC 续航 605km…",
    source: "电车汇 / 36氪",
    date: "2026-05-30",
  },
  {
    title: "工信部发布 2026 新能源汽车下乡车型推荐目录",
    summary:
      "工信部 5 月 28 日发布 2026 年度新能源汽车下乡车型推荐目录申报通知。比亚迪元 PLUS、五菱缤果、长安 Lumin 等 30 余款车型入围…",
    source: "工信部官网 / 中汽协",
    date: "2026-05-28",
  },
];
