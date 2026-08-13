#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/nev-brief}"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/ai-generate-$(TZ=Asia/Shanghai date +%Y%m%d).log"
mkdir -p "$LOG_DIR"
UV_BIN="$(command -v uv 2>/dev/null || true)"
[[ -n "$UV_BIN" ]] || UV_BIN="$HOME/.local/bin/uv"
[[ -x "$UV_BIN" ]] || { echo "uv not found" | tee -a "$LOG_FILE" >&2; exit 1; }
cd "$PROJECT_ROOT"
echo "[$(date -u +%FT%TZ)] generate starting" | tee -a "$LOG_FILE"
set +e
TZ=Asia/Shanghai "$UV_BIN" run python -m ai_brief generate --date "$(TZ=Asia/Shanghai date +%F)" 2>&1 | tee -a "$LOG_FILE"
code=${PIPESTATUS[0]}
set -e
echo "[$(date -u +%FT%TZ)] generate finished exit=$code" | tee -a "$LOG_FILE"
exit "$code"
