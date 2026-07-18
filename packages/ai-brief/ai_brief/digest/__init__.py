"""Digest 摄取层 —— 今日AI / AI大神 两模块从 Gmail digest 邮件取内容。

不走 crawler：
  今日AI  ← ai-events-digest-<GMT+8当日>  (HTML, 3 条, 附件 01/02/03-*.png)
  AI大神  ← follow-builder-digest-<GMT+8当日> (纯文本, 10 条, 附件 tweet_6..10.png)

parsers 是纯函数（输入邮件正文字符串），便于 fixture 测试、不触网。
IMAP 抓取 / Qwen 选图 / DeepSeek 压缩另在各自模块。
"""
