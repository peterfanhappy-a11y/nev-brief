#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GEN="$ROOT/ops/launchd/com.aivizens.ai-generate.plist"
GEN_RUN="$ROOT/ops/launchd/run-ai-generate.sh"
INSTALL="$ROOT/ops/launchd/install-ai-daily.sh"

for path in "$GEN" "$GEN_RUN" "$INSTALL"; do
  [[ -f "$path" ]] || { echo "missing: $path" >&2; exit 1; }
done

plutil -lint "$GEN" >/dev/null
grep -q '<string>com.aivizens.ai-generate</string>' "$GEN"
[[ "$(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:0' "$GEN")" == "/usr/bin/caffeinate" ]] \
  || { echo 'generate job must run under caffeinate' >&2; exit 1; }
[[ "$(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:1' "$GEN")" == "-s" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:2' "$GEN")" == "/bin/bash" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:0:Hour' "$GEN")" == "8" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:0:Minute' "$GEN")" == "10" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:1:Hour' "$GEN")" == "9" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:1:Minute' "$GEN")" == "10" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:2:Hour' "$GEN")" == "10" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval:2:Minute' "$GEN")" == "10" ]]
[[ ! -e "$ROOT/ops/launchd/com.aivizens.ai-release.plist" ]] \
  || { echo 'legacy release plist must be removed' >&2; exit 1; }
[[ ! -e "$ROOT/ops/launchd/run-ai-release.sh" ]] \
  || { echo 'legacy release runner must be removed' >&2; exit 1; }

if grep -R -n -- 'python -m ai_brief daily' "$GEN_RUN"; then
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
if [[ " ${*} " == *" python -m ai_brief approve "* && "${FAKE_APPROVE_STATUS:-0}" != "0" ]]; then
  exit "$FAKE_APPROVE_STATUS"
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
RUN_DATE="$(TZ=Asia/Shanghai date +%F)"
cat > "$TMP_DIR/expected-trace" <<EOF
run python -m ai_brief generate --date $RUN_DATE --skip-existing
run python -m ai_brief approve --date $RUN_DATE
run python -m ai_brief release --date $RUN_DATE
run python -m ai_brief deliver --date $RUN_DATE --retry-transient
EOF
diff -u "$TMP_DIR/expected-trace" "$TMP_DIR/trace"

: > "$TMP_DIR/trace"
if TRACE_FILE="$TMP_DIR/trace" PATH="$TMP_DIR/bin:$PATH" PROJECT_ROOT="$TMP_DIR/project" \
  FAKE_GENERATE_STATUS=1 bash "$GEN_RUN"; then
  echo 'failed generate unexpectedly succeeded' >&2
  exit 1
fi
if grep -Eq 'python -m ai_brief (approve|release|deliver) --date' "$TMP_DIR/trace"; then
  echo 'later step ran after failed generate' >&2
  exit 1
fi

: > "$TMP_DIR/trace"
if TRACE_FILE="$TMP_DIR/trace" PATH="$TMP_DIR/bin:$PATH" PROJECT_ROOT="$TMP_DIR/project" \
  FAKE_APPROVE_STATUS=1 bash "$GEN_RUN"; then
  echo 'failed approve unexpectedly succeeded' >&2
  exit 1
fi
if grep -Eq 'python -m ai_brief (release|deliver) --date' "$TMP_DIR/trace"; then
  echo 'release or deliver ran after failed approve' >&2
  exit 1
fi

: > "$TMP_DIR/trace"
if TRACE_FILE="$TMP_DIR/trace" PATH="$TMP_DIR/bin:$PATH" PROJECT_ROOT="$TMP_DIR/project" \
  FAKE_RELEASE_STATUS=1 bash "$GEN_RUN"; then
  echo 'failed release unexpectedly succeeded' >&2
  exit 1
fi
if grep -q 'python -m ai_brief deliver --date' "$TMP_DIR/trace"; then
  echo 'deliver ran after failed release' >&2
  exit 1
fi

: > "$TMP_DIR/trace"
if TRACE_FILE="$TMP_DIR/trace" PATH="$TMP_DIR/bin:$PATH" PROJECT_ROOT="$TMP_DIR/project" \
  FAKE_DELIVER_STATUS=1 bash "$GEN_RUN"; then
  echo 'failed deliver unexpectedly succeeded' >&2
  exit 1
fi
grep -q 'python -m ai_brief deliver --date' "$TMP_DIR/trace"

# Exercise installation in an isolated fake HOME. The legacy release agent is
# booted out and its plist removed, while only the caffeinated cycle is loaded.
TEST_HOME="$TMP_DIR/home"
TEST_PROJECT="$TMP_DIR/custom-project"
mkdir -p "$TEST_PROJECT/ops/launchd" "$TEST_HOME/Library/LaunchAgents"
cp "$GEN" "$GEN_RUN" "$INSTALL" "$TEST_PROJECT/ops/launchd/"
touch "$TEST_HOME/Library/LaunchAgents/com.aivizens.ai-release.plist"
cat > "$TMP_DIR/bin/launchctl" <<'FAKE_LAUNCHCTL'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$LAUNCHCTL_TRACE"
if [[ "$*" == *"com.aivizens.ai-release"* ]]; then
  if [[ "$1" == "print" ]]; then
    [[ "${FAKE_RELEASE_STUCK:-0}" == "1" ]] && exit 0 || exit 1
  fi
  if [[ "$1" == "bootout" && "${FAKE_RELEASE_STUCK:-0}" == "1" ]]; then
    exit 1
  fi
fi
exit 0
FAKE_LAUNCHCTL
chmod +x "$TMP_DIR/bin/launchctl"
LAUNCHCTL_TRACE="$TMP_DIR/launchctl-trace" HOME="$TEST_HOME" \
  PROJECT_ROOT="$TEST_PROJECT" PATH="$TMP_DIR/bin:$PATH" bash "$TEST_PROJECT/ops/launchd/install-ai-daily.sh"
[[ -f "$TEST_HOME/Library/LaunchAgents/com.aivizens.ai-generate.plist" ]]
[[ ! -e "$TEST_HOME/Library/LaunchAgents/com.aivizens.ai-release.plist" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :WorkingDirectory' "$TEST_HOME/Library/LaunchAgents/com.aivizens.ai-generate.plist")" == "$TEST_PROJECT" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:3' "$TEST_HOME/Library/LaunchAgents/com.aivizens.ai-generate.plist")" == "$TEST_PROJECT/ops/launchd/run-ai-generate.sh" ]]
grep -q 'bootout .*com.aivizens.ai-release' "$TMP_DIR/launchctl-trace"
grep -q 'bootstrap .*com.aivizens.ai-generate.plist' "$TMP_DIR/launchctl-trace"
if grep -q 'bootstrap .*com.aivizens.ai-release.plist' "$TMP_DIR/launchctl-trace"; then
  echo 'legacy release agent was bootstrapped' >&2
  exit 1
fi

touch "$TEST_HOME/Library/LaunchAgents/com.aivizens.ai-release.plist"
if LAUNCHCTL_TRACE="$TMP_DIR/launchctl-stuck-trace" HOME="$TEST_HOME" \
  PROJECT_ROOT="$TEST_PROJECT" PATH="$TMP_DIR/bin:$PATH" FAKE_RELEASE_STUCK=1 \
  bash "$TEST_PROJECT/ops/launchd/install-ai-daily.sh"; then
  echo 'install unexpectedly succeeded while legacy release agent remained loaded' >&2
  exit 1
fi
[[ -f "$TEST_HOME/Library/LaunchAgents/com.aivizens.ai-release.plist" ]]

echo 'launchd schedule contract ok'
