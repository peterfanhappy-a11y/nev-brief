#!/usr/bin/env bash
# ops/launchd/run-ai-daily.sh
# launchd 每天 06:10 调用，跑 AIVIZENS AI 趋势每日简报（与 NEV run-daily.sh 平行独立）。
#
# 手动测试：PROJECT_ROOT=$HOME/nev-brief ./ops/launchd/run-ai-daily.sh
set -u

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/nev-brief}"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/ai-daily-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

# 代理隔离在 Python 内做（httpx trust_env=False + resend no_proxy_env），
# 此处不动 shell 的 HTTP_PROXY 等，保持与 run-daily.sh 一致。

# 定位 uv：先 PATH，再常见安装点
UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -z "$UV_BIN" ]]; then
    for cand in "$HOME/.local/bin/uv" "/opt/homebrew/bin/uv" "/usr/local/bin/uv"; do
        if [[ -x "$cand" ]]; then UV_BIN="$cand"; break; fi
    done
fi
if [[ -z "$UV_BIN" || ! -x "$UV_BIN" ]]; then
    echo "[$(date -u +%FT%TZ)] FATAL: uv not found" | tee -a "$LOG_FILE" >&2
    exit 1
fi

cd "$PROJECT_ROOT" || {
    echo "[$(date -u +%FT%TZ)] FATAL: project root $PROJECT_ROOT not found" \
        | tee -a "$LOG_FILE" >&2
    exit 1
}

echo "[$(date -u +%FT%TZ)] ai-daily run starting (uv=$UV_BIN)" | tee -a "$LOG_FILE"

"$UV_BIN" run python -m ai_brief daily 2>&1 | tee -a "$LOG_FILE"
exit_code=${PIPESTATUS[0]}

echo "[$(date -u +%FT%TZ)] ai-daily run finished, exit=$exit_code" | tee -a "$LOG_FILE"
exit "$exit_code"
