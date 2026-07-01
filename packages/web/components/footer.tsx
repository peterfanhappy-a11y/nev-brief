import Link from "next/link";

const SOCIAL = [
  { name: "微博", href: "#", icon: "W" },
  { name: "抖音", href: "#", icon: "D" },
  { name: "小红书", href: "#", icon: "X" },
  { name: "快手", href: "#", icon: "K" },
];

export default function Footer() {
  return (
    <footer className="border-t border-gray-100 bg-gray-50 py-12 mt-16">
      <div className="max-w-6xl mx-auto px-6">
        <div className="flex flex-col items-center gap-6 text-center">
          <Link href="/" aria-label="AIVIZENS 首页">
            <img src="/brand/logo.svg" alt="AIVIZENS" className="h-10 w-auto" />
          </Link>
          <p className="max-w-xl text-sm text-gray-600 leading-relaxed">
            每日 3 分钟，跟上最新 AI 新闻、趋势与工具。加入 100 万+ 专业人士。
          </p>
          <div className="flex items-center gap-3">
            {SOCIAL.map((s) => (
              <a
                key={s.name}
                href={s.href}
                aria-label={s.name}
                title={s.name}
                className="inline-flex items-center justify-center h-10 w-10 rounded-full border border-gray-200 bg-white text-sm font-semibold text-gray-700 hover:bg-gray-900 hover:text-white transition-colors"
              >
                {s.icon}
              </a>
            ))}
          </div>
          <div className="text-xs text-gray-400 pt-4 border-t border-gray-200 w-full max-w-md">
            © 2026 AIVIZENS ·{" "}
            <Link href="/nev" className="hover:text-gray-700">NEV 早报</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
