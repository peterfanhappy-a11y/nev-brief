#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GEN="$ROOT/ops/launchd/com.aivizens.ai-generate.plist"
REL="$ROOT/ops/launchd/com.aivizens.ai-release.plist"
GEN_RUN="$ROOT/ops/launchd/run-ai-generate.sh"
REL_RUN="$ROOT/ops/launchd/run-ai-release.sh"

for path in "$GEN" "$REL" "$GEN_RUN" "$REL_RUN"; do
  [[ -f "$path" ]] || { echo "missing: $path" >&2; exit 1; }
done

plutil -lint "$GEN" >/dev/null
plutil -lint "$REL" >/dev/null

grep -q '<string>com.aivizens.ai-generate</string>' "$GEN"
[[ "$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:Hour' "$GEN")" == "8" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:Minute' "$GEN")" == "10" ]]
grep -q '<string>com.aivizens.ai-release</string>' "$REL"
[[ "$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:Hour' "$REL")" == "8" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:Minute' "$REL")" == "45" ]]
grep -q 'ai-generate-.*\.log' "$GEN_RUN"
grep -q 'ai-release-.*\.log' "$REL_RUN"
grep -q 'source "$PROJECT_ROOT/.env"' "$GEN_RUN"
grep -q 'source "$PROJECT_ROOT/.env"' "$REL_RUN"
grep -q 'python -m ai_brief generate' "$GEN_RUN"
grep -q 'python -m ai_brief release' "$REL_RUN"
if grep -R -n -- 'python -m ai_brief daily' "$GEN_RUN" "$REL_RUN"; then
  echo 'retired daily command found' >&2
  exit 1
fi

# Exercise the runner sequence with a disposable fake uv; no production DB/API is touched.
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
mkdir -p "$TMP_DIR/bin" "$TMP_DIR/project"
cat > "$TMP_DIR/bin/uv" <<'FAKE_UV'
#!/usr/bin/env bash
set -u
printf '%s\n' "$*" >> "$TRACE_FILE"
if [[ " ${*} " == *" python -m ai_brief generate "* && "${FAKE_GENERATE_STATUS:-0}" != "0" ]]; then
  exit "$FAKE_GENERATE_STATUS"
fi
if [[ " ${*} " == *" python -m ai_brief release "* && "${FAKE_RELEASE_STATUS:-0}" != "0" ]]; then
  exit "$FAKE_RELEASE_STATUS"
fi
if [[ " ${*} " == *" python -m ai_brief deliver "* && "${FAKE_DELIVER_STATUS:-0}" != "0" ]]; then
  exit "$FAKE_DELIVER_STATUS"
fi
exit 0
FAKE_UV
chmod +x "$TMP_DIR/bin/uv"
TRACE_FILE="$TMP_DIR/trace" PATH="$TMP_DIR/bin:$PATH" PROJECT_ROOT="$TMP_DIR/project" \
  AIVIZENS_OPERATOR_ID=test-operator bash "$GEN_RUN"
grep -q 'python -m ai_brief approve --date' "$TMP_DIR/trace"
: > "$TMP_DIR/trace"
if TRACE_FILE="$TMP_DIR/trace" PATH="$TMP_DIR/bin:$PATH" PROJECT_ROOT="$TMP_DIR/project" \
  FAKE_GENERATE_STATUS=1 bash "$GEN_RUN"; then
  echo 'failed generate unexpectedly succeeded' >&2
  exit 1
fi
if grep -q 'python -m ai_brief approve --date' "$TMP_DIR/trace"; then
  echo 'approve ran after failed generate' >&2
  exit 1
fi

: > "$TMP_DIR/trace"
TRACE_FILE="$TMP_DIR/trace" PATH="$TMP_DIR/bin:$PATH" PROJECT_ROOT="$TMP_DIR/project" \
  bash "$REL_RUN"
grep -q 'python -m ai_brief release --date' "$TMP_DIR/trace"
grep -q 'python -m ai_brief deliver --date' "$TMP_DIR/trace"
: > "$TMP_DIR/trace"
if TRACE_FILE="$TMP_DIR/trace" PATH="$TMP_DIR/bin:$PATH" PROJECT_ROOT="$TMP_DIR/project" \
  FAKE_RELEASE_STATUS=1 bash "$REL_RUN"; then
  echo 'failed release unexpectedly succeeded' >&2
  exit 1
fi
if grep -q 'python -m ai_brief deliver --date' "$TMP_DIR/trace"; then
  echo 'deliver ran after failed release' >&2
  exit 1
fi
: > "$TMP_DIR/trace"
if TRACE_FILE="$TMP_DIR/trace" PATH="$TMP_DIR/bin:$PATH" PROJECT_ROOT="$TMP_DIR/project" \
  FAKE_DELIVER_STATUS=1 bash "$REL_RUN"; then
  echo 'failed deliver unexpectedly succeeded' >&2
  exit 1
fi
grep -q 'python -m ai_brief deliver --date' "$TMP_DIR/trace"

echo 'launchd schedule contract ok'
