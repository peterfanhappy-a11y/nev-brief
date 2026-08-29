# Mac mini launchd 部署

 AIVIZENS 在 Mac Mini 上拆为 06:45 生成/质量通过后自动审批与 08:00 发布投递；NEV 旧任务保持独立。

## 安装（一键）

把项目 clone 到 `$HOME/nev-brief`（或导出 `PROJECT_ROOT` 覆盖），然后：

```bash
bash ops/launchd/install-ai-daily.sh
```

脚本会自动：
1. 检查 `uv` 是否装好
2. 把两个 AIVIZENS plist 里的 `REPLACE_ME` 替换成 `$HOME`
3. 拷到 `~/Library/LaunchAgents/`
4. `launchctl bootstrap`
5. 创建 `logs/` 目录

## 验证

```bash
launchctl print gui/$(id -u)/com.aivizens.ai-generate
launchctl print gui/$(id -u)/com.aivizens.ai-release
```

## 手动 trigger（测试）

```bash
launchctl kickstart gui/$(id -u)/com.aivizens.ai-generate
launchctl kickstart gui/$(id -u)/com.aivizens.ai-release
```

## 卸载

```bash
launchctl unload ~/Library/LaunchAgents/com.nev.daily.plist
rm ~/Library/LaunchAgents/com.nev.daily.plist
```

## 升级 / 重新安装

直接重跑 `install-daily.sh` — 它会先 `unload` 旧的再加载新的。

## 文件说明

- `com.aivizens.ai-generate.plist` / `com.aivizens.ai-release.plist` — 两个任务模板
- `run-ai-generate.sh` / `run-ai-release.sh` — 生成与发布 runner
- `install-ai-daily.sh` — 一键安装两个 AIVIZENS 任务
- `README.md` — 你正在看的这个

## 注意

- Mac mini 系统时区必须是 Asia/Shanghai，否则 06:00 不准（`sudo systemsetup -settimezone Asia/Shanghai`）
- 笔记本/Mac mini 必须保持开机；Sleep 时 launchd 不会 wake（要 wake 用 `pmset repeat wakeorpoweron MTWRFSU 05:55:00`）
- `.env` 必须在 `PROJECT_ROOT` 根目录（orchestrator 通过 dotenv 加载）
- 06:45 任务生成日报；只有生成命令以 0 退出（质量门禁通过）时才自动执行 `approve`。
- 08:00 任务只发布已批准内容并排空投递队列；请确认 `PROJECT_ROOT/.env` 中 `AI_EMAIL_SEND_ENABLED=true` 才会实际发送。
- 质量阻断或生成失败时不会审批、发布或发送；失败详情写入 `logs/ai-generate-YYYYMMDD.log`。
