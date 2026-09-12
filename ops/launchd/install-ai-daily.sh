#!/usr/bin/env bash
# ops/launchd/install-ai-daily.sh
# Mac mini 一键安装 AIVIZENS AI 趋势每日简报 launchd（与 install-daily.sh 平行独立）。
#
# 用法：bash ops/launchd/install-ai-daily.sh
# 假定项目在 $HOME/nev-brief；路径不同先 export PROJECT_ROOT=...
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/nev-brief}"
PLIST_GEN="$PROJECT_ROOT/ops/launchd/com.aivizens.ai-generate.plist"
DEST_GEN="$HOME/Library/LaunchAgents/com.aivizens.ai-generate.plist"
LEGACY_DEST_REL="$HOME/Library/LaunchAgents/com.aivizens.ai-release.plist"
RUN_GEN="$PROJECT_ROOT/ops/launchd/run-ai-generate.sh"

if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo "❌ PROJECT_ROOT 不存在: $PROJECT_ROOT" >&2
    exit 1
fi
if [[ ! -f "$PLIST_GEN" ]]; then
    echo "❌ generate plist 模板缺失" >&2
    exit 1
fi
if [[ ! -f "$RUN_GEN" ]]; then
    echo "❌ generate runner 脚本缺失" >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1 \
    && [[ ! -x "$HOME/.local/bin/uv" ]] \
    && [[ ! -x "/opt/homebrew/bin/uv" ]] \
    && [[ ! -x "/usr/local/bin/uv" ]]; then
    echo "❌ uv 未安装。先装：curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

chmod +x "$RUN_GEN"
mkdir -p "$PROJECT_ROOT/logs"

launchctl bootout "gui/$(id -u)/com.aivizens.ai-generate" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/com.aivizens.ai-release" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/com.aivizens.ai-daily" 2>/dev/null || true
if launchctl print "gui/$(id -u)/com.aivizens.ai-release" >/dev/null 2>&1; then
    echo "❌ 旧 release agent 仍在运行，停止安装以免留下无 plist 的任务" >&2
    exit 1
fi
rm -f "$LEGACY_DEST_REL"

mkdir -p "$HOME/Library/LaunchAgents"
sed "s|REPLACE_ME/nev-brief|$PROJECT_ROOT|g" "$PLIST_GEN" > "$DEST_GEN"
echo "→ 写入 $DEST_GEN"

launchctl bootstrap "gui/$(id -u)" "$DEST_GEN"
echo "→ launchctl bootstrap OK"

if launchctl print "gui/$(id -u)/com.aivizens.ai-generate" >/dev/null 2>&1; then
    echo ""
    echo "✅ AIVIZENS 完整周期 08:10/09:10/10:10 已注册"
    echo ""
    echo "手动测一次:"
    echo "  launchctl kickstart gui/$(id -u)/com.aivizens.ai-generate"
    echo ""
    echo "卸载:"
    echo "  launchctl bootout gui/$(id -u)/com.aivizens.ai-generate"
else
    echo "❌ 加载后没在 launchctl list 里看到，请检查 plist 语法" >&2
    exit 1
fi
