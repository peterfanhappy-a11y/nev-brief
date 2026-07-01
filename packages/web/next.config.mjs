/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async redirects() {
    // NEV 早报 landing + 详情页从 / 搬到 /nev/*。老邮件里的 aivizens.com/d/YYYY-MM-DD
    // 链接通过 301 兜住不 404。旧 /api/subscribe 同样跳到 /api/nev/subscribe。
    return [
      { source: "/d/:path*", destination: "/nev/d/:path*", permanent: true },
      { source: "/api/subscribe", destination: "/api/nev/subscribe", permanent: true },
    ];
  },
};

export default nextConfig;
