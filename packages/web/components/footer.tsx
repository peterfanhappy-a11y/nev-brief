import Link from "next/link";
import { BrandIcon } from "@/components/brand-icon";

const SOCIAL: { slug: string; name: string; href: string }[] = [
  { slug: "sinaweibo", name: "微博", href: "#" },
  { slug: "douyin", name: "抖音", href: "#" },
  { slug: "xiaohongshu", name: "小红书", href: "#" },
  { slug: "kuaishou", name: "快手", href: "#" },
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
            每日 5 分钟，跟上最新 AI 新闻、趋势与工具。加入 10 万+ 专业人士。
          </p>
          <div className="flex items-center gap-3">
            {SOCIAL.map((s) => (
              <a
                key={s.slug}
                href={s.href}
                aria-label={s.name}
                title={s.name}
                className="inline-flex items-center justify-center h-11 w-11 rounded-full bg-white border border-gray-200 text-gray-600 hover:bg-gray-900 hover:text-white hover:border-gray-900 transition-colors"
              >
                <BrandIcon slug={s.slug} size={22} title={s.name} />
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
