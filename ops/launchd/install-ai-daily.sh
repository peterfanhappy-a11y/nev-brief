#!/usr/bin/env bash
# ops/launchd/install-ai-daily.sh
# Mac mini 一键安装 AIVIZENS AI 趋势每日简报 launchd（与 install-daily.sh 平行独立）。
#
# 用法：bash ops/launchd/install-ai-daily.sh
# 假定项目在 $HOME/nev-brief；路径不同先 export PROJECT_ROOT=...
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/nev-brief}"
PLIST_SRC="$PROJECT_ROOT/ops/launchd/com.aivizens.ai-daily.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.aivizens.ai-daily.plist"
RUNNER="$PROJECT_ROOT/ops/launchd/run-ai-daily.sh"

if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo "❌ PROJECT_ROOT 不存在: $PROJECT_ROOT" >&2
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

if ! command -v uv >/dev/null 2>&1 \
    && [[ ! -x "$HOME/.local/bin/uv" ]] \
    && [[ ! -x "/opt/homebrew/bin/uv" ]] \
    && [[ ! -x "/usr/local/bin/uv" ]]; then
    echo "❌ uv 未安装。先装：curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

chmod +x "$RUNNER"
mkdir -p "$PROJECT_ROOT/logs"

if launchctl list | grep -q "com.aivizens.ai-daily"; then
    echo "→ 卸载已有 com.aivizens.ai-daily..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

mkdir -p "$HOME/Library/LaunchAgents"
sed "s|REPLACE_ME|$HOME|g" "$PLIST_SRC" > "$PLIST_DEST"
echo "→ 写入 $PLIST_DEST"

launchctl load "$PLIST_DEST"
echo "→ launchctl load OK"

if launchctl list | grep -q "com.aivizens.ai-daily"; then
    echo ""
    echo "✅ com.aivizens.ai-daily 已注册，每天 06:10 自动跑（NEV 06:00 之后错峰）"
    echo ""
    echo "手动测一次:"
    echo "  launchctl start com.aivizens.ai-daily"
    echo "  tail -f $PROJECT_ROOT/logs/ai-daily-\$(date +%Y%m%d).log"
    echo ""
    echo "卸载:"
    echo "  launchctl unload $PLIST_DEST"
else
    echo "❌ 加载后没在 launchctl list 里看到，请检查 plist 语法" >&2
    exit 1
fi
