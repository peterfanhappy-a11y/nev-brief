import Link from "next/link";

export default function Header() {
  return (
    <header className="sticky top-0 z-40 bg-white/85 backdrop-blur border-b border-gray-100">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2" aria-label="AIVIZENS 首页">
          {/* 用 logo.svg 作为默认；用户在 T2 后 pick v1/v2/v3 会 rename 生效 */}
          <img
            src="/brand/logo.svg"
            alt="AIVIZENS"
            className="h-8 w-auto"
          />
        </Link>
        <a
          href="#subscribe"
          className="inline-flex items-center rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 transition-colors"
        >
          订阅
        </a>
      </div>
    </header>
  );
}
