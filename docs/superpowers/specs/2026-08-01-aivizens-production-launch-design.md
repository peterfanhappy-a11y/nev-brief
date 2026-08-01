# AIVIZENS AI 日报生产上线与 NEV 退役设计

**日期：** 2026-08-01  
**状态：** 已批准，可进入分阶段实施
**目标产品：** AIVIZENS AI 日报  
**生产域名：** `https://aivizens.com`  
**发件身份：** `AIVIZENS 趋势 <aivizens.daily@aivizens.com>`

## 1. 背景与结论

仓库最初实现新能源汽车行业早报（NEV），随后增加并转向 AIVIZENS AI 日报。当前 AI 日报已经具备 Gmail Digest 摄取、DeepSeek 内容加工、Qwen 选图、Supabase 存储、邮件渲染、Resend 投递、退订、评分和 Mac Mini 定时任务，但网站仍展示 mock 内容，订阅接口没有生产级防滥用和邮箱确认，发布过程也缺少正式审核状态。

本次采用“分阶段收敛”方案：先建立稳定工程基线，再完成 AI 日报订阅、内容归档、审核发布和运维闭环；经过影子运行后备份并彻底退役 NEV，最后开放正式订阅。每个阶段都有独立验收和回退点。

## 2. 已确认的产品决策

1. AIVIZENS 是唯一主产品，NEV 完全退役。
2. 删除 NEV 前后端代码、测试、调度和文档。
3. NEV 线上数据先导出为可恢复 SQL 备份并验证，随后在最终切换阶段删除。
4. 原 `/nev` 及历史 NEV URL 返回 `410 Gone`，不跳转、不保留退役页。
5. 第一阶段保留外部 Hermes 定时任务和 Gmail Digest 输入。
6. 后续单独实现 Hermes Markdown 直读和 Hermes Agent 产出评估，不纳入首发。
7. 首发范围为生产可用上线，不建设完整运营后台和商业化模块。
8. 新订阅采用 double opt-in、服务端 Turnstile 校验和限流。
9. 正式上线前清空现有 `ai_subscribers`；关联投递和评分按外键级联清除。
10. 现有 AI 历史日报、文章和图片暂时保留。
11. 公开网站采用“每日一期完整归档”，不建设单条新闻详情页。
12. 每日北京时间 06:45 生成，人工批准后北京时间 08:00 发布和发信。
13. 未设置自动切换日期；在用户明确授权前始终人工批准。
14. 审核通过由 Mac Mini CLI 完成，网页只提供受保护的只读预览。
15. 品牌、域名、产品名和发件身份保持现状。
16. 首发包含基础数据库视图和 CLI 统计，不包含完整管理后台、打开率追踪或用户画像。
17. “10 万+读者”和公司 Logo 背书在当前版本暂时保留；最终上线时不再要求删除。
18. 当前没有正式社交账号，`href="#"` 社交入口暂时保留；最终上线时不再要求删除。
19. 用户已授权最终阶段在完成备份验证后删除线上 NEV 数据、清空 AI 订阅者、执行生产部署并开放订阅。实际执行不可逆生产操作前仍需按安全规范核对精确目标。

## 3. 范围

### 3.1 首发范围

- 修复测试、CI、依赖和环境文档基线。
- 收敛代码库为 AIVIZENS AI 日报单产品。
- 实现生产级 double opt-in 订阅流程。
- 实现 Digest 摄取契约、运行记录和内容质量门禁。
- 实现日报审核状态、签名预览、CLI 批准和 08:00 发布。
- 实现公开日报归档、真实首页内容和 SEO/Sitemap。
- 实现安全退订、评分确认、投递幂等和失败恢复。
- 实现基础运营统计和飞书告警。
- 备份、验证并删除 NEV 数据；删除 NEV 代码与部署配置。
- 部署生产版本并完成上线验收。

### 3.2 首发不包含

- 完整运营后台。
- 赞助、广告、付费订阅或工具推广。
- 用户栏目偏好和个性化日报。
- 单条新闻详情页。
- Hermes Markdown 直读。
- Hermes Agent 质量评估系统。
- 自动批准或自动发信切换。
- 邮件打开率、跨站行为追踪或用户画像。

## 4. 目标架构

```text
Hermes 定时任务
    ↓
五类 Gmail Digest
    ↓
GmailDigestAdapter
    ↓
摄取契约与运行记录
    ↓
DeepSeek 选择/压缩 + Qwen 选图
    ↓
质量门禁
    ├── 不合格 → blocked + 飞书告警
    └── 合格 → awaiting_approval
                    ↓
           签名只读预览 + CLI approve
                    ↓
                 approved
                    ↓ 08:00
        ┌───────────┴───────────┐
        ↓                       ↓
公开日报 /daily/YYYY-MM-DD   ai_deliveries → Resend
```

输入端定义稳定的 `DigestInputAdapter` 接口。首发只实现 `GmailDigestAdapter`；后续新增 `HermesMarkdownAdapter` 时不改变校验、加工、审核、发布和投递组件。

## 5. 组件边界

### 5.1 输入适配器

职责：获取指定日期的五类 Digest，并返回统一的来源描述、原始内容、附件和时间信息。

首发来源：

- `ai-events-digest-*`
- `follow-builder-digest-*`
- `ai-research-digest-*`
- `ai-engineering-digest-*`
- `ai-agent-digest-*`

Gmail 账号、应用密码和代理配置只从环境变量读取。运行记录保存邮件 Message-ID、主题、时间和解析摘要，不默认保存完整邮件正文或凭据。

### 5.2 内容加工

职责：解析 Digest，调用 DeepSeek 进行选择和摘要，调用 Qwen 选择图片，并生成单一 `AiBriefContent` 文档。链接和来源由程序从输入注入，模型不能自行创造来源 URL。

### 5.3 质量门禁

职责：验证栏目完整性、来源新鲜度、链接、结构、字数、重复内容和占位符，生成机器可读 `quality_report`，决定日报进入 `blocked` 或 `awaiting_approval`。

### 5.4 审核与发布

职责：提供短期签名只读预览；CLI 执行批准；08:00 任务仅发布已批准内容。批准后的内容冻结，发布和投递期间不得再次调用模型或覆盖正文。

### 5.5 Web

职责：首页订阅与真实日报列表、完整日报归档、邮箱确认、退订确认、评分确认、SEO/Sitemap 和 NEV 410。

### 5.6 投递

职责：为 active 订阅者创建独立投递记录，使用每日订阅者级幂等键发送，记录成功、临时失败和永久失败，提供显式重试命令与全局发信开关。

## 6. 数据模型

### 6.1 `ai_subscribers`

状态：

```text
pending_confirmation → active → unsubscribed
        ↑                           │
        └────── 重新订阅 ────────────┘
```

新增字段：

- `confirmation_token_hash`
- `confirmation_expires_at`
- `confirmed_at`
- `unsubscribed_at`
- `signup_ip_hash`
- `utm_source`
- `utm_medium`
- `utm_campaign`

确认令牌使用高熵随机值，只保存哈希，24 小时失效。重复提交和未知邮箱均返回相同响应，避免泄露订阅状态。重新订阅必须重新确认。

### 6.2 `ai_daily_briefs`

状态：

```text
generating ──失败──> blocked
    │
    └──通过──> awaiting_approval → approved → published
```

新增字段：

- `status`
- `quality_report jsonb`
- `digest_sources jsonb`
- `approved_at`
- `published_at`
- `failure_reason`

同一日期只能有一个日报。已批准或已发布日报不能被日常生成任务覆盖。

### 6.3 `ai_digest_runs`

新增运行表，记录：

- `brief_date`
- 开始、结束和耗时
- 五类 Digest 的到达、日期回退和解析数量
- Message-ID、主题和邮件时间
- 内容加工结果
- 质量门禁结论
- 失败阶段和安全错误摘要

### 6.4 `ai_deliveries` 与 `ai_ratings`

保留现有投递和评分表。投递状态仍为 `pending → sending → sent/failed/bounced`。评分改为用户在确认页主动提交后写入，避免邮件扫描器访问 GET 链接造成误评分。

### 6.5 基础统计

提供数据库视图和 `ai_brief stats` CLI，包含：

- pending、confirmed、active、unsubscribed 人数。
- 订阅确认率。
- 每日生成、阻断、批准、发布状态。
- sent、failed、pending、retry 数量。
- 每期评分分布。
- Digest 缺失、日期回退和解析异常数量。

## 7. 核心业务流程

### 7.1 订阅

```text
提交邮箱
→ 服务端校验 Turnstile
→ IP/邮箱限流
→ pending_confirmation
→ 发送确认邮件
→ 用户点击有效确认链接
→ active
→ 发送欢迎邮件
```

接口返回统一成功提示。确认链接只能使用一次；过期后允许重新发送，但受到限流保护。

### 7.2 生成、审核与发布

1. 06:45 任务为当天创建运行记录并摄取 Digest。
2. 解析、加工并生成质量报告。
3. 不合格则标记 `blocked` 并告警。
4. 合格则标记 `awaiting_approval` 并生成短期签名预览 URL。
5. 人工检查后在 Mac Mini 执行 `ai_brief approve --date YYYY-MM-DD`。
6. 08:00 发布器只处理 `approved` 日报，事务性地标记发布并创建投递记录。
7. 投递器逐条发送并独立提交结果。
8. 08:00 时未批准则不发布、不发信，只告警。
9. 08:00 后批准不会自动补发；需要显式执行 `ai_brief release --date YYYY-MM-DD`。

### 7.3 退订与评分

打开普通退订链接只展示确认页，用户提交 POST 后才改变状态。邮件同时支持标准 `List-Unsubscribe-Post` 一键退订协议。评分链接先进入确认页，用户明确提交后才写入数据库。

## 8. 质量门禁

### 8.1 硬性阻断

- “今日 AI”缺失或少于 3 条。
- “AI 大神”少于 3 条。
- 工具学习三个栏目中少于 2 个可用。
- Schema 校验失败。
- 主题、导语或关键链接缺失。
- 链接非法或内容包含明显占位符。
- Digest 超出允许的新鲜度窗口。
- DeepSeek 输出重试后仍不完整。
- 当天已有已批准或已发布日报。

### 8.2 审核警告

- 工具学习缺少一个栏目。
- Qwen 选图失败并降级为无图。
- 使用 40 小时内的日期回退 Digest。
- 非核心条目被过滤。
- 摘要接近字数上限。
- 出现首次见到的来源域名。

## 9. 网站信息架构

### 9.1 首页 `/`

- 保留现有 AIVIZENS 品牌和“每日 5 分钟学会 AI”定位。
- 展示最近 6 期真实已发布日报。
- 每期展示日期、主题、导语和主要栏目。
- 删除所有 mock 新闻和无效“阅读全文”链接。
- 页面首屏和底部提供订阅入口。
- 按用户明确决定，暂时保留“10 万+读者”、公司 Logo 背书及 `href="#"` 社交入口。

### 9.2 日报归档 `/daily/YYYY-MM-DD`

- 展示完整一期五大栏目、图片和来源链接。
- 显示发布日期和预计阅读时间。
- 支持前一期/后一期导航和订阅 CTA。
- 只有 `published` 日报公开访问。
- 未发布日报返回 404；预览使用独立签名 URL。

### 9.3 SEO

- Sitemap 只收录首页和已发布日报。
- 每期生成 canonical、OpenGraph 和描述元数据。
- NEV URL 不进入 Sitemap，并返回 410。

## 10. NEV 退役设计

### 10.1 代码退役

删除以下 NEV 专属内容：

- `packages/composer`
- `packages/delivery`
- `packages/orchestrator`
- `packages/summarizer`
- NEV Web 页面、API、组件和数据访问代码
- 根目录 NEV 单元、集成、性能和 golden tests
- NEV launchd/Windows 调度文件
- NEV 里程碑文档和过时 README 内容

AI 当前仍引用部分 NEV 命名包，不能直接整目录删除：

- `nev_pipeline.deepseek_client` 必须先迁入 `ai_brief` 或通用基础包。
- `nev_crawler.robots.RobotsChecker` 必须先迁入 AI crawler 或通用基础包。
- `nev_shared` 中配置、日志、网络、重试和飞书能力仍被 AI 使用，应保留并重命名为中性基础包，或明确作为兼容包继续存在。
- `nev_contracts` 和其他未被 AI 使用的依赖在依赖图清理后删除。

完成依赖迁移并通过 AI 回归测试后，才删除 `packages/pipeline` 和 `packages/crawler`。

### 10.2 数据备份

对以下 NEV 表执行可恢复 SQL 导出：

- `subscribers`
- `subscriber_preferences`
- `sources`
- `articles_raw`
- `articles_processed`
- `daily_briefs`
- `vehicle_sales_daily`
- `deliveries`

备份存放于 Mac Mini 的受限目录，不提交 Git。验证内容包括文件哈希、表结构、每表行数、关键记录抽样和在临时数据库中的恢复演练。

### 10.3 数据删除

恢复验证成功后，按外键依赖顺序删除上述 NEV 表、索引、触发器和策略。共享的 `touch_updated_at()` 函数被 AI 表使用，必须保留。历史迁移文件不直接篡改；新增独立 retire migration 记录生产删除动作。

### 10.4 路由退役

`/nev`、`/nev/d/*`、NEV API 和旧管理入口返回 `410 Gone`。实现以明确的 410 路由/中间件为准，不用 301 或普通 404。

## 11. 错误处理与恢复

- Gmail/IMAP：有限重试；失败后记录运行并阻断。
- DeepSeek：指数退避和结构重试；核心摘要失败则阻断。
- Qwen：有限重试；失败允许无图并发出警告。
- Supabase：关键状态和投递创建使用事务，避免半发布。
- Resend：订阅者级幂等；临时故障回到 pending，永久故障标记 failed。
- 部分邮件失败不回滚已成功邮件，也不撤回公开归档。
- P0/P1 故障通过飞书发送日期、阶段、错误摘要和恢复命令。
- 全局发信开关可停止 Resend，而不停止内容生成和审核。

## 12. 测试与 CI

### 12.1 Phase 0 基线修复

- 修复多个顶层 `tests` 包造成的 pytest 收集冲突。
- 正确标记和隔离数据库、网络、真实 Resend 和真实模型测试。
- 安装并配置 Vitest，修复根 `npm test`。
- 清理 Ruff/ESLint 阻断问题，建立可执行 lint 基线。
- 保持 Next.js 类型检查和生产构建通过。

### 12.2 新增测试

- 订阅令牌、过期、重复提交、重新订阅和限流单元测试。
- Digest 契约、质量门禁和日报状态机单元测试。
- CLI approve/release/stats 和发布幂等测试。
- Postgres/Supabase 集成测试。
- Web 订阅、确认、归档、退订、评分和 NEV 410 测试。
- 浏览器 E2E：新用户提交、确认、成为 active 和可进入投递队列。
- HTML/text 邮件渲染、退订头、链接和移动端布局验证。
- 现有 53 个 AI 日报测试持续通过。

### 12.3 CI 门禁

```text
Python 单元测试
+ Web 单元测试
+ TypeScript 类型检查
+ Next.js 生产构建
+ Ruff/ESLint
```

真实网络、模型、数据库和邮件 E2E 作为受控验收任务，不在普通 PR 中自动触发。

## 13. 分阶段交付

### Phase 0：工程基线与资产盘点

修复测试、CI、依赖和环境文档；记录 Vercel、Supabase、Resend、Gmail、飞书和 Mac Mini 配置；建立发布回退点。

**门禁：** 主干可重复安装、测试、检查和构建。

### Phase 1：正式订阅与数据状态

实现 double opt-in、Turnstile 服务端校验、限流、令牌和订阅状态迁移；提供受控清空现有 AI 订阅者的生产操作。

**门禁：** 未确认邮箱无法进入投递；接口不能被简单绕过或用于批量欢迎邮件攻击。

### Phase 2：真实内容网站

实现日报状态字段、公开归档、首页真实内容、SEO/Sitemap；删除 mock 新闻。按已确认决策保留读者/公司背书和空社交入口。

**门禁：** 网站不再展示 mock 日报，只有已发布内容公开。

### Phase 3：审核、调度与可观察性

实现运行记录、质量报告、签名预览、CLI approve/release/stats、06:45 生成、08:00 发布、飞书告警、全局发信开关和失败恢复。

**门禁：** 至少完成一次不向真实订阅者发信的影子运行，以及一次指定测试邮箱的完整 E2E。

### Phase 4：NEV 退役与生产切换

导出并恢复验证 SQL 备份；迁移 AI 对 NEV 包的残留依赖；删除 NEV 代码、测试、任务和文档；部署 410；删除 NEV 线上数据。

**门禁：** 备份可恢复、AI 回归测试通过、生产目标已精确核对。

### Phase 5：正式上线与人工运营

清空现有 AI 订阅者，部署生产版本，开放 double opt-in 订阅，每日保持人工批准，监控订阅、发布、投递、退订和评分。

**完成条件：** 全部首发验收标准通过，生产 smoke test 成功，无未处理 P0/P1 故障。

## 14. 部署与回退

### 14.1 部署顺序

1. 部署向后兼容的数据库新增迁移。
2. 部署 Vercel 预览环境并验证 Web 流程。
3. Mac Mini 安装新任务但仅 dry-run。
4. 执行 Digest → 预览 → 批准 → 测试邮箱投递 E2E。
5. 完成 NEV SQL 备份和恢复演练。
6. 部署 NEV 410 和代码清理版本。
7. 执行生产数据清理、正式部署和公开订阅开放。

### 14.2 回退

- 每个 Phase 独立提交并标记可回退版本。
- Web 可回退到上一版 Vercel 部署。
- 早期数据库迁移只新增字段和表，不删除数据。
- 生产问题可关闭订阅和发信开关，同时保留首页与内容生成。
- NEV 删除使用独立 retire migration；恢复依赖已验证 SQL 备份。
- 已批准内容不可被自动重新生成，避免回退过程中内容漂移。

## 15. 首发验收标准

- 首页展示真实已发布日报。
- `/daily/YYYY-MM-DD` 可访问完整日报。
- 新用户只有完成 double opt-in 才能收到邮件。
- 退订和评分不会被 GET 预取误触发。
- 06:45 生成、人工批准、08:00 发布和投递按状态机运行。
- 未批准或质量不合格日报绝不发送。
- 重复执行发布或投递不会重复发送。
- NEV 代码、测试、任务和文档已删除；旧 URL 返回 410。
- NEV SQL 备份已经恢复验证，线上 NEV 数据已删除。
- 现有 AI 订阅者已清空，正式订阅从零开始。
- 基础统计和飞书告警可用。
- CI 门禁和生产 smoke test 全部通过。
- `aivizens.com` 使用确认的品牌和发件身份正式开放订阅。

## 16. 后续演进

Hermes 集成后续采用独立规格和计划，顺序为：

```text
邮件摄取稳定运行
→ 增加 HermesMarkdownAdapter
→ 邮件/Markdown 双读对比
→ 建立 Hermes 输出质量评分
→ Markdown 成为主输入
→ 邮件保留为应急回退
```

运营后台、个性化、单条内容页和商业化同样作为独立项目评估，不扩展本次首发范围。
