# Mac mini launchd 部署

跟 Windows (`ops/windows/`) 对位 — 都是 06:00 daily 触发 orchestrator。

## 安装（一键）

把项目 clone 到 `$HOME/nev-brief`（或导出 `PROJECT_ROOT` 覆盖），然后：

```bash
bash ops/launchd/install-daily.sh
```

脚本会自动：
1. 检查 `uv` 是否装好
2. 把 `com.nev.daily.plist` 里的 `REPLACE_ME` 替换成 `$HOME`
3. 拷到 `~/Library/LaunchAgents/`
4. `launchctl load`
5. 创建 `logs/` 目录

## 验证

```bash
launchctl list | grep com.nev.daily
```

## 手动 trigger（测试）

```bash
launchctl start com.nev.daily
tail -f ~/nev-brief/logs/daily-$(date +%Y%m%d).log
```

## 卸载

```bash
launchctl unload ~/Library/LaunchAgents/com.nev.daily.plist
rm ~/Library/LaunchAgents/com.nev.daily.plist
```

## 升级 / 重新安装

直接重跑 `install-daily.sh` — 它会先 `unload` 旧的再加载新的。

## 文件说明

- `com.nev.daily.plist` — launchd 模板，含 `REPLACE_ME` 占位符
- `run-daily.sh` — 真正的 runner（cd 到项目根、定位 uv、跑 orchestrator、tee 日志）
- `install-daily.sh` — 一键安装脚本
- `README.md` — 你正在看的这个

## 注意

- Mac mini 系统时区必须是 Asia/Shanghai，否则 06:00 不准（`sudo systemsetup -settimezone Asia/Shanghai`）
- 笔记本/Mac mini 必须保持开机；Sleep 时 launchd 不会 wake（要 wake 用 `pmset repeat wakeorpoweron MTWRFSU 05:55:00`）
- `.env` 必须在 `PROJECT_ROOT` 根目录（orchestrator 通过 dotenv 加载）
- 后续 Hermes Agent 主调度 + launchd 兜底见 spec §7.5
