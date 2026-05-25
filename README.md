# NEV 早报

新能源汽车行业 B 端 AI 早报订阅产品。每日 8:00 推送 10 条精选新闻 + 主要车企日销量数据。

## 文档
- 设计 spec: `docs/superpowers/specs/2026-05-24-nev-morning-brief-design.md`
- 主调度计划: `docs/superpowers/plans/2026-05-24-nev-master-plan.md`
- Agent-0 基础设施计划: `docs/superpowers/plans/2026-05-24-nev-agent-0-foundation.md`

## 快速开始
```bash
make dev    # 起本地 Postgres + RSSHub
make test   # 跑全部测试
```

## 模块
- `packages/contracts` — 数据模型共享契约
- `packages/shared` — 通用工具（db / logger / retry / config）
- `packages/crawler` — 信源爬取（Agent-2）
- `packages/pipeline` — 清洗去重打分（Agent-3）
- `packages/summarizer` — AI 摘要（Agent-4）
- `packages/composer` — 个性化拼装（Agent-5）
- `packages/delivery` — 邮件推送（Agent-6）
- `packages/monitor` — 监控告警（Agent-7）
- `packages/web` — Next.js 落地页（Agent-1）
