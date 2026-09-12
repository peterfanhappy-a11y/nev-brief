# Mac mini launchd 部署

AIVIZENS 在 Mac Mini 上以单一任务依次完成生成、审批、发布和投递；NEV 旧任务保持独立。

## 安装（一键）

把项目 clone 到 `$HOME/nev-brief`（或导出 `PROJECT_ROOT` 覆盖），然后：

```bash
bash ops/launchd/install-ai-daily.sh
```

脚本会自动：
1. 检查 `uv` 是否装好
2. 把 AIVIZENS plist 里的 `REPLACE_ME` 替换成 `$HOME`
3. 拷到 `~/Library/LaunchAgents/`
4. `launchctl bootstrap`
5. 创建 `logs/` 目录
6. 卸载并删除旧的独立 release agent

## 验证

```bash
launchctl print gui/$(id -u)/com.aivizens.ai-generate
```

## 手动 trigger（测试）

```bash
launchctl kickstart gui/$(id -u)/com.aivizens.ai-generate
```

## 卸载

```bash
launchctl bootout gui/$(id -u)/com.aivizens.ai-generate
rm ~/Library/LaunchAgents/com.aivizens.ai-generate.plist
```

## 升级 / 重新安装

直接重跑 `install-ai-daily.sh` — 它会先卸载旧任务再加载新的。

## 文件说明

- `com.aivizens.ai-generate.plist` — 08:10/09:10/10:10 三次幂等重试模板
- `run-ai-generate.sh` — `generate → approve → release → deliver` 完整周期 runner
- `install-ai-daily.sh` — 一键安装 AIVIZENS 任务
- `README.md` — 你正在看的这个

## 注意

- Mac mini 系统时区必须是 Asia/Shanghai，否则触发时间不准（`sudo systemsetup -settimezone Asia/Shanghai`）
- Sleep 时 launchd 不会主动唤醒 Mac，任务可能延迟到下次唤醒后运行；本次按运营约定暂不修改系统休眠设置。
- 任务启动后由 `caffeinate -s` 保持系统唤醒，直到生成、审批、发布和投递全部结束。
- `.env` 必须在 `PROJECT_ROOT` 根目录（orchestrator 通过 dotenv 加载）
- 完整周期在 08:10、09:10、10:10 重试；每一步只有在上一步以 0 退出时才继续。
- 发布与投递不再依赖固定的 release 时刻；请确认 `PROJECT_ROOT/.env` 中 `AI_EMAIL_SEND_ENABLED=true` 才会实际发送。
- 已发布日期会幂等跳过生成和发布；临时发送失败会在后续周期重新排队，最多重试 3 次。
- 质量阻断或生成失败时不会审批、发布或发送；失败详情写入 `logs/ai-generate-YYYYMMDD.log`。
