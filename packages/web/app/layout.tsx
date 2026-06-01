import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NEV 早报 · 新能源汽车行业每日精选",
  description: "每天早上 8:00 送达 · 10 条精选新闻 + 主要车企日销量数据",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="bg-gray-50 antialiased font-sans">{children}</body>
    </html>
  );
}
