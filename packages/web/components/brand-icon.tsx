// Brand logo renderer with two-tier resolution:
//   1. LOCAL_PNG — user-supplied PNG in /public/brand/companies/ (preferred)
//   2. MONOGRAM  — generic colored-circle + character fallback (currently empty;
//                  every brand in use has a PNG asset)
type MonogramSpec = { char: string; bg: string };

// Local PNGs live under /public/brand/companies/. Every brand shown on the
// AI landing (hero trust bar + footer socials) is served from here.
const LOCAL_PNG: Record<string, string> = {
  bytedance: "/brand/companies/bytedance.png",
  alibaba: "/brand/companies/alibaba.png",
  tencent: "/brand/companies/tencent.png",
  deepseek: "/brand/companies/deepseek.png",
  xiaomi: "/brand/companies/xiaomi.png",
  huawei: "/brand/companies/huawei.png",
  weibo: "/brand/companies/weibo.png",
  wechat: "/brand/companies/wechat.png",
  douyin: "/brand/companies/douyin.png",
  xiaohongshu: "/brand/companies/xiaohongshu.png?v=2",
};

const MONOGRAM: Record<string, MonogramSpec> = {};

export function BrandIcon({
  slug,
  size = 32,
  className = "",
  title,
}: {
  slug: string;
  size?: number;
  className?: string;
  title?: string;
}) {
  const localSrc = LOCAL_PNG[slug];
  if (localSrc) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={localSrc}
        alt={title ?? slug}
        style={{
          height: size,
          width: "auto",
          maxWidth: size * 3.5,
          objectFit: "contain",
        }}
        className={className}
        loading="lazy"
        decoding="async"
      />
    );
  }

  const mono = MONOGRAM[slug];
  if (mono) {
    return (
      <div
        role="img"
        aria-label={title ?? slug}
        title={title ?? slug}
        className={`inline-flex items-center justify-center rounded-full font-bold text-white ${className}`}
        style={{
          width: size,
          height: size,
          backgroundColor: mono.bg,
          fontSize: mono.char.length > 1 ? size * 0.4 : size * 0.5,
          lineHeight: 1,
        }}
      >
        {mono.char}
      </div>
    );
  }

  return null;
}
