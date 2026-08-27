import Link from "next/link";
import React from "react";

export default function BriefSubscribeCta() {
  return (
    <aside className="rounded-2xl bg-gray-900 px-6 py-10 text-center text-white sm:px-10">
      <h2 className="text-2xl font-bold">每天 5 分钟，跟上 AI 进展</h2>
      <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-gray-300">
        订阅 AIVIZENS，把下一期精选日报直接发送到你的邮箱。
      </p>
      <Link
        href="/#subscribe"
        className="mt-6 inline-flex rounded-md bg-white px-5 py-2.5 text-sm font-semibold text-gray-900 transition-colors hover:bg-gray-100"
      >
        免费订阅 AIVIZENS
      </Link>
    </aside>
  );
}
