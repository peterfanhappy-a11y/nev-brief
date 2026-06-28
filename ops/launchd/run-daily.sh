#!/usr/bin/env bash
# ops/launchd/run-daily.sh
# launchd 每天 06:00 调用（与 Windows ops/windows/run-daily.ps1 对位）。
#
# 用法：launchd 通过 plist 直接执行；手动测试可以：
#   PROJECT_ROOT=$HOME/nev-brief ./ops/launchd/run-daily.sh
set -u

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/nev-brief}"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/daily-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

# Proxy isolation is done inside Python (trust_env=False on every httpx client,
# no_proxy_env() contextmanager around the resend SDK call). This shell keeps
# whatever HTTP_PROXY/HTTPS_PROXY/ALL_PROXY the cron environment inherits — we
# do NOT unset them globally because that would surprise anyone reusing this
# script outside cron and is unnecessary given the in-process opt-out.

# 定位 uv：先 PATH，再常见安装点
UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -z "$UV_BIN" ]]; then
    for cand in "$HOME/.local/bin/uv" "/opt/homebrew/bin/uv" "/usr/local/bin/uv"; do
        if [[ -x "$cand" ]]; then UV_BIN="$cand"; break; fi
    done
fi
if [[ -z "$UV_BIN" || ! -x "$UV_BIN" ]]; then
    echo "[$(date -u +%FT%TZ)] FATAL: uv not found in PATH or common install locations" \
        | tee -a "$LOG_FILE" >&2
    exit 1
fi

cd "$PROJECT_ROOT" || {
    echo "[$(date -u +%FT%TZ)] FATAL: project root $PROJECT_ROOT not found" \
        | tee -a "$LOG_FILE" >&2
    exit 1
}

echo "[$(date -u +%FT%TZ)] daily run starting (uv=$UV_BIN)" | tee -a "$LOG_FILE"

# stderr 合并到 stdout，再 tee 进日志；exit code 通过 PIPESTATUS 捕获
"$UV_BIN" run python -m nev_orchestrator daily 2>&1 | tee -a "$LOG_FILE"
exit_code=${PIPESTATUS[0]}

echo "[$(date -u +%FT%TZ)] daily run finished, exit=$exit_code" | tee -a "$LOG_FILE"
exit "$exit_code"
