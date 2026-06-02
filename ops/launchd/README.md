# Mac mini launchd 部署

## 安装

```bash
# 1. 替换 REPLACE_ME 为实际用户名
sed -i '' "s/REPLACE_ME/$USER/g" ~/nev-brief/ops/launchd/com.nev.daily.plist

# 2. 复制到 LaunchAgents
cp ~/nev-brief/ops/launchd/com.nev.daily.plist ~/Library/LaunchAgents/

# 3. 创建日志目录
mkdir -p ~/nev-brief/logs

# 4. 加载
launchctl load ~/Library/LaunchAgents/com.nev.daily.plist
```

## 验证

```bash
launchctl list | grep com.nev.daily
```

## 手动 trigger

```bash
launchctl start com.nev.daily
tail -f ~/nev-brief/logs/launchd-daily.log
```

## 卸载

```bash
launchctl unload ~/Library/LaunchAgents/com.nev.daily.plist
rm ~/Library/LaunchAgents/com.nev.daily.plist
```

## 注意

- `uv` 必须在 `/Users/<you>/.local/bin/uv`，否则改 plist 第一个 ProgramArguments
- Mac mini 时区必须是 Asia/Shanghai，否则 06:00 不准
- 后续 Hermes Agent 主调度 + launchd 兜底见 spec §7.5
