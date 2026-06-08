#!/usr/bin/env bash
# ops/launchd/install-daily.sh
# Mac mini 一键安装：把 com.nev.daily.plist 替换占位符、装到 LaunchAgents、加载。
#
# 用法：bash ops/launchd/install-daily.sh
# 假定项目克隆到 $HOME/nev-brief；如果路径不同，先 export PROJECT_ROOT=...
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/nev-brief}"
PLIST_SRC="$PROJECT_ROOT/ops/launchd/com.nev.daily.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.nev.daily.plist"
RUNNER="$PROJECT_ROOT/ops/launchd/run-daily.sh"

if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo "❌ PROJECT_ROOT 不存在: $PROJECT_ROOT" >&2
    echo "   请 git clone 到该路径，或 export PROJECT_ROOT=/path/to/nev-brief" >&2
    exit 1
fi
if [[ ! -f "$PLIST_SRC" ]]; then
    echo "❌ plist 模板缺失: $PLIST_SRC" >&2
    exit 1
fi
if [[ ! -f "$RUNNER" ]]; then
    echo "❌ runner 脚本缺失: $RUNNER" >&2
    exit 1
fi

# uv 必装；不同位置都接受
if ! command -v uv >/dev/null 2>&1 \
    && [[ ! -x "$HOME/.local/bin/uv" ]] \
    && [[ ! -x "/opt/homebrew/bin/uv" ]] \
    && [[ ! -x "/usr/local/bin/uv" ]]; then
    echo "❌ uv 未安装。先装：curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

# 让 runner 可执行
chmod +x "$RUNNER"

# 日志目录
mkdir -p "$PROJECT_ROOT/logs"

# 卸载旧版本（如果已加载）
if launchctl list | grep -q "com.nev.daily"; then
    echo "→ 卸载已有 com.nev.daily..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# 替换 REPLACE_ME → $HOME，写到 LaunchAgents
mkdir -p "$HOME/Library/LaunchAgents"
sed "s|REPLACE_ME|$HOME|g" "$PLIST_SRC" > "$PLIST_DEST"
echo "→ 写入 $PLIST_DEST"

# 加载
launchctl load "$PLIST_DEST"
echo "→ launchctl load OK"

# 验证
if launchctl list | grep -q "com.nev.daily"; then
    echo ""
    echo "✅ com.nev.daily 已注册，每天 06:00 自动跑"
    echo ""
    echo "手动测一次:"
    echo "  launchctl start com.nev.daily"
    echo "  tail -f $PROJECT_ROOT/logs/daily-\$(date +%Y%m%d).log"
    echo ""
    echo "卸载:"
    echo "  launchctl unload $PLIST_DEST"
else
    echo "❌ 加载后没在 launchctl list 里看到，请检查 plist 语法" >&2
    exit 1
fi
