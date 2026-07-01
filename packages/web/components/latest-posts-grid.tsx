"use client";

import { useState } from "react";
import { MOCK_AI_POSTS, POSTS_PER_PAGE, type AIPost } from "@/lib/mock-ai-posts";

function PostCard({ post }: { post: AIPost }) {
  return (
    <article className="group bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all overflow-hidden flex flex-col">
      <div
        className={`h-40 bg-gradient-to-br ${post.cover} flex items-end p-4`}
      >
        <span className="inline-flex items-center rounded-full bg-white/90 backdrop-blur px-2.5 py-1 text-xs font-medium text-gray-800">
          {post.tag}
        </span>
      </div>
      <div className="flex-1 p-5 flex flex-col">
        <h3 className="font-semibold text-gray-900 mb-2 leading-snug group-hover:text-indigo-600 transition-colors">
          {post.title}
        </h3>
        <p className="text-sm text-gray-600 leading-relaxed mb-4 flex-1">
          {post.summary}
        </p>
        <div className="flex items-center justify-between text-xs text-gray-400 pt-3 border-t border-gray-50">
          <time dateTime={post.date}>{post.date}</time>
          <a href="#" className="text-indigo-600 hover:text-indigo-700 font-medium">
            阅读全文 →
          </a>
        </div>
      </div>
    </article>
  );
}

export default function LatestPostsGrid() {
  const [visible, setVisible] = useState(POSTS_PER_PAGE);
  const posts = MOCK_AI_POSTS.slice(0, visible);
  const hasMore = visible < MOCK_AI_POSTS.length;

  return (
    <section className="max-w-6xl mx-auto px-6 py-16">
      <div className="flex items-end justify-between mb-8">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">最新文章</h2>
          <p className="text-sm text-gray-500 mt-1">
            每日精选，覆盖模型、工具、趋势、监管全景
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {posts.map((p) => (
          <PostCard key={p.slug} post={p} />
        ))}
      </div>
      {hasMore && (
        <div className="mt-10 flex justify-center">
          <button
            type="button"
            onClick={() =>
              setVisible((v) => Math.min(v + POSTS_PER_PAGE, MOCK_AI_POSTS.length))
            }
            className="inline-flex items-center rounded-md border border-gray-200 bg-white px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors"
          >
            加载更多
          </button>
        </div>
      )}
    </section>
  );
}
