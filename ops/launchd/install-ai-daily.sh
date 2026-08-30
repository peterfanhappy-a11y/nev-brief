#!/usr/bin/env bash
# ops/launchd/install-ai-daily.sh
# Mac mini 一键安装 AIVIZENS AI 趋势每日简报 launchd（与 install-daily.sh 平行独立）。
#
# 用法：bash ops/launchd/install-ai-daily.sh
# 假定项目在 $HOME/nev-brief；路径不同先 export PROJECT_ROOT=...
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/nev-brief}"
PLIST_GEN="$PROJECT_ROOT/ops/launchd/com.aivizens.ai-generate.plist"
PLIST_REL="$PROJECT_ROOT/ops/launchd/com.aivizens.ai-release.plist"
DEST_GEN="$HOME/Library/LaunchAgents/com.aivizens.ai-generate.plist"
DEST_REL="$HOME/Library/LaunchAgents/com.aivizens.ai-release.plist"
RUN_GEN="$PROJECT_ROOT/ops/launchd/run-ai-generate.sh"
RUN_REL="$PROJECT_ROOT/ops/launchd/run-ai-release.sh"

if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo "❌ PROJECT_ROOT 不存在: $PROJECT_ROOT" >&2
    exit 1
fi
if [[ ! -f "$PLIST_GEN" || ! -f "$PLIST_REL" ]]; then
    echo "❌ generate/release plist 模板缺失" >&2
    exit 1
fi
if [[ ! -f "$RUN_GEN" || ! -f "$RUN_REL" ]]; then
    echo "❌ generate/release runner 脚本缺失" >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1 \
    && [[ ! -x "$HOME/.local/bin/uv" ]] \
    && [[ ! -x "/opt/homebrew/bin/uv" ]] \
    && [[ ! -x "/usr/local/bin/uv" ]]; then
    echo "❌ uv 未安装。先装：curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

chmod +x "$RUN_GEN" "$RUN_REL"
mkdir -p "$PROJECT_ROOT/logs"

launchctl bootout "gui/$(id -u)/com.aivizens.ai-generate" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/com.aivizens.ai-release" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/com.aivizens.ai-daily" 2>/dev/null || true

mkdir -p "$HOME/Library/LaunchAgents"
sed "s|REPLACE_ME|$HOME|g" "$PLIST_GEN" > "$DEST_GEN"
sed "s|REPLACE_ME|$HOME|g" "$PLIST_REL" > "$DEST_REL"
echo "→ 写入 $DEST_GEN 和 $DEST_REL"

launchctl bootstrap "gui/$(id -u)" "$DEST_GEN"
launchctl bootstrap "gui/$(id -u)" "$DEST_REL"
echo "→ launchctl bootstrap OK"

if launchctl print "gui/$(id -u)/com.aivizens.ai-generate" >/dev/null 2>&1 \
   && launchctl print "gui/$(id -u)/com.aivizens.ai-release" >/dev/null 2>&1; then
    echo ""
    echo "✅ AIVIZENS generate 08:10 / release 08:45 已注册"
    echo ""
    echo "手动测一次:"
    echo "  launchctl kickstart gui/$(id -u)/com.aivizens.ai-generate"
    echo "  launchctl kickstart gui/$(id -u)/com.aivizens.ai-release"
    echo ""
    echo "卸载:"
    echo "  launchctl bootout gui/$(id -u)/com.aivizens.ai-generate"
    echo "  launchctl bootout gui/$(id -u)/com.aivizens.ai-release"
else
    echo "❌ 加载后没在 launchctl list 里看到，请检查 plist 语法" >&2
    exit 1
fi
