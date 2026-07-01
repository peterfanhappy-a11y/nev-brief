import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIVIZENS · 每日 AI 精选",
  description: "每日 5 分钟，学会 AI。最新 AI 资讯、行业趋势与实用工具。",
  icons: {
    icon: "/favicon.svg",
  },
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
