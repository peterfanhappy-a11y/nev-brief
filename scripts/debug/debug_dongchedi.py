"""探测懂车帝 Next.js 页面的 __NEXT_DATA__ JSON，找文章列表的路径。

用法: uv run python debug_dongchedi.py
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from selectolax.parser import HTMLParser

URL = "https://www.dongchedi.com/news"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def walk(obj: Any, path: str = "", max_depth: int = 6) -> list[tuple[str, int]]:
    """遍历 JSON，返回所有 list[dict] 的 path 和长度。"""
    results: list[tuple[str, int]] = []
    if max_depth <= 0:
        return results
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}" if path else k
            results.extend(walk(v, new_path, max_depth - 1))
    elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
        results.append((path, len(obj)))
        if len(obj) >= 1:
            results.extend(walk(obj[0], f"{path}[0]", max_depth - 1))
    return results


def find_article_arrays(data: dict) -> None:
    """找所有 length >= 5 的 dict 列表（候选文章列表）。"""
    arrays = walk(data)
    candidates = [(p, n) for p, n in arrays if 5 <= n <= 100]
    print(f"\n候选文章列表 (5-100 项):")
    for path, n in sorted(candidates, key=lambda x: -x[1])[:15]:
        print(f"  {n:>3d} items  at  {path}")


def sample_first_item(data: dict, path: str) -> None:
    """打印某 path 下第一项的字段（帮助识别 title/url 在哪个字段）。"""
    parts = path.split(".")
    cur: Any = data
    for p in parts:
        if "[" in p:
            key, idx = p.split("[")
            idx = int(idx.rstrip("]"))
            cur = cur[key][idx] if key else cur[idx]
        else:
            cur = cur.get(p) if isinstance(cur, dict) else None
            if cur is None:
                return
    if isinstance(cur, list) and cur:
        first = cur[0]
        print(f"\n首项字段 ({path}[0]):")
        for k, v in first.items() if isinstance(first, dict) else []:
            val_str = str(v)[:80] if not isinstance(v, (dict, list)) else f"<{type(v).__name__}>"
            print(f"  {k:<25s} = {val_str}")


async def main() -> None:
    async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        resp = await client.get(URL)
        print(f"HTTP {resp.status_code}  body={len(resp.text)} chars")

        tree = HTMLParser(resp.text)
        script = tree.css_first("script#__NEXT_DATA__")
        if not script:
            print("❌ 没找到 <script id='__NEXT_DATA__'>")
            return
        raw = script.text()
        print(f"✅ __NEXT_DATA__ 找到，{len(raw)} chars")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {e}")
            return

        # 顶层结构
        print(f"\n顶层键: {list(data.keys())}")

        # 找候选文章列表
        find_article_arrays(data)

        # 自动抽样前 3 个候选的首项字段
        arrays = walk(data)
        candidates = sorted(
            [(p, n) for p, n in arrays if 5 <= n <= 100],
            key=lambda x: -x[1],
        )[:3]
        for path, _ in candidates:
            sample_first_item(data, path)


if __name__ == "__main__":
    asyncio.run(main())
