"""crawler 纯函数测试 — article 解析 / feed 解析 / listing 解析。不触网。"""
from __future__ import annotations

from ai_brief.crawler.article import extract_content, extract_og_image, extract_title
from ai_brief.crawler.feeds import parse_feed
from ai_brief.crawler.listing import parse_listing

ARTICLE_HTML = """
<html><head>
  <title>页面标题 - 站点名</title>
  <meta property="og:title" content="真正的文章标题">
  <meta property="og:image" content="https://cdn.example.com/cover.jpg">
  <meta name="description" content="这是一段兜底描述文本。">
</head><body>
  <nav>导航不该进正文</nav>
  <article>
    <h1>真正的文章标题</h1>
    <p>这是第一段正文，足够长以通过两百字符阈值判断，需要更多内容填充这里，所以我继续写更多更多的中文字符来确保达到阈值要求，满满当当，反复强调重点信息，补充上下文背景，让这段文字显得像真实的新闻报道正文而不是占位符。</p>
    <p>这是第二段正文，继续补充信息，让正文块显著大于其他区域，从而被启发式选中作为主要文本区域，内容繁多，细节丰富，覆盖事件的来龙去脉、各方反应以及后续影响，充分模拟真实文章的篇幅结构。</p>
    <script>should_be_dropped()</script>
  </article>
  <footer>页脚不该进正文</footer>
</body></html>
"""


def test_extract_og_image() -> None:
    assert extract_og_image(ARTICLE_HTML) == "https://cdn.example.com/cover.jpg"


def test_extract_og_image_rejects_non_https() -> None:
    html = '<meta property="og:image" content="http://insecure.com/x.jpg">'
    assert extract_og_image(html) is None


def test_extract_og_image_twitter_fallback() -> None:
    html = '<meta name="twitter:image" content="https://cdn.x.com/t.png">'
    assert extract_og_image(html) == "https://cdn.x.com/t.png"


def test_extract_title_prefers_og() -> None:
    assert extract_title(ARTICLE_HTML) == "真正的文章标题"


def test_extract_content_from_article() -> None:
    content = extract_content(ARTICLE_HTML)
    assert content is not None
    assert "第一段正文" in content
    assert "导航不该进正文" not in content
    assert "页脚不该进正文" not in content
    assert "should_be_dropped" not in content


def test_extract_content_meta_fallback() -> None:
    html = (
        '<html><head><meta name="description" content="仅有描述兜底">'
        "</head><body><p>短</p></body></html>"
    )
    assert extract_content(html) == "仅有描述兜底"


def test_parse_feed() -> None:
    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>文章一</title><link>https://a.com/1</link>
        <description>这是文章一的摘要内容。</description>
        <pubDate>Wed, 02 Jul 2026 10:00:00 GMT</pubDate></item>
      <item><title>文章二</title><link>https://a.com/2</link></item>
      <item><title></title><link>https://a.com/3</link></item>
    </channel></rss>"""
    entries = parse_feed(rss)
    assert len(entries) == 2  # 第三条无标题被丢
    assert entries[0].url == "https://a.com/1"
    assert entries[0].summary == "这是文章一的摘要内容。"
    assert entries[0].published_at is not None
    assert entries[1].summary is None
    assert entries[1].published_at is None


def test_parse_listing_resolves_relative() -> None:
    html = """<html><body>
      <a class="post" href="/news/item-1">标题一</a>
      <a class="post" href="https://x.com/news/item-2">标题二</a>
      <a class="post" href="/news/item-1">重复</a>
    </body></html>"""
    links = parse_listing(
        html, base_url="https://x.com/news", link_selector="a.post", link_attr="href"
    )
    assert len(links) == 2  # 去重
    assert links[0].url == "https://x.com/news/item-1"
    assert links[0].title == "标题一"
