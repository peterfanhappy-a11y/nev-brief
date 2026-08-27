import type { Metadata } from "next";

import { siteBaseUrl } from "@/lib/site-url";

import "./globals.css";

const title = "AIVIZENS · 每日 AI 精选";
const description = "每日 5 分钟，学会 AI。最新 AI 资讯、行业趋势与实用工具。";

export const metadata: Metadata = {
  metadataBase: new URL(siteBaseUrl()),
  title,
  description,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "AIVIZENS",
    title,
    description,
    locale: "zh_CN",
  },
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
