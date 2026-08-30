#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/nev-brief}"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/ai-release-$(TZ=Asia/Shanghai date +%Y%m%d).log"
mkdir -p "$LOG_DIR"
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi
UV_BIN="$(command -v uv 2>/dev/null || true)"
[[ -n "$UV_BIN" ]] || UV_BIN="$HOME/.local/bin/uv"
[[ -x "$UV_BIN" ]] || { echo "uv not found" | tee -a "$LOG_FILE" >&2; exit 1; }
cd "$PROJECT_ROOT"
echo "[$(date -u +%FT%TZ)] release starting" | tee -a "$LOG_FILE"
set +e
RUN_DATE="$(TZ=Asia/Shanghai date +%F)"
TZ=Asia/Shanghai "$UV_BIN" run python -m ai_brief release --date "$RUN_DATE" 2>&1 | tee -a "$LOG_FILE"
code=${PIPESTATUS[0]}
if [[ "$code" -eq 0 ]]; then
    echo "[$(date -u +%FT%TZ)] deliver starting" | tee -a "$LOG_FILE"
    TZ=Asia/Shanghai "$UV_BIN" run python -m ai_brief deliver --date "$RUN_DATE" 2>&1 | tee -a "$LOG_FILE"
    code=${PIPESTATUS[0]}
    echo "[$(date -u +%FT%TZ)] deliver finished exit=$code" | tee -a "$LOG_FILE"
fi
set -e
echo "[$(date -u +%FT%TZ)] release finished exit=$code" | tee -a "$LOG_FILE"
exit "$code"
