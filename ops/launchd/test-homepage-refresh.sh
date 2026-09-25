#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REFRESH="$ROOT/ops/launchd/refresh-ai-homepage.sh"
RUNNER="$ROOT/ops/launchd/run-ai-generate.sh"
TEST_DATE="2026-09-24"

[[ -x "$REFRESH" ]] || { echo "missing executable: $REFRESH" >&2; exit 1; }

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
mkdir -p "$TMP_DIR/bin" "$TMP_DIR/project"

cat > "$TMP_DIR/bin/curl" <<'FAKE_CURL'
#!/usr/bin/env bash
set -u
printf '%s\n' "$*" >> "$HTTP_TRACE"
if [[ " $* " == *" --request POST "* ]]; then
  [[ "${FAKE_REVALIDATE_FAIL:-0}" == "1" ]] && exit 22
  printf '{"ok":true}\n'
  exit 0
fi
count=0
[[ -f "$GET_COUNT_FILE" ]] && count="$(cat "$GET_COUNT_FILE")"
count=$((count + 1))
printf '%s' "$count" > "$GET_COUNT_FILE"
if [[ "${FAKE_HOMEPAGE_ALWAYS_STALE:-0}" != "1" && "$count" -ge 2 ]]; then
  printf '<a href="/daily/%s">today</a>\n' "$TEST_DATE"
else
  printf '<a href="/daily/2026-09-23">yesterday</a>\n'
fi
FAKE_CURL

cat > "$TMP_DIR/bin/sleep" <<'FAKE_SLEEP'
#!/usr/bin/env bash
exit 0
FAKE_SLEEP

cat > "$TMP_DIR/bin/uv" <<'FAKE_UV'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$TRACE_FILE"
exit 0
FAKE_UV

chmod +x "$TMP_DIR/bin/curl" "$TMP_DIR/bin/sleep" "$TMP_DIR/bin/uv"

HTTP_TRACE="$TMP_DIR/http-trace"
GET_COUNT_FILE="$TMP_DIR/get-count"
export HTTP_TRACE GET_COUNT_FILE TEST_DATE

if PATH="$TMP_DIR/bin:$PATH" HOMEPAGE_REVALIDATE_SECRET="" \
  "$REFRESH" "$TEST_DATE"; then
  echo "refresh unexpectedly accepted a missing secret" >&2
  exit 1
fi
[[ ! -s "$HTTP_TRACE" ]]

: > "$HTTP_TRACE"
if PATH="$TMP_DIR/bin:$PATH" HOMEPAGE_REVALIDATE_SECRET="too-short" \
  "$REFRESH" "$TEST_DATE"; then
  echo "refresh unexpectedly accepted a short secret" >&2
  exit 1
fi
[[ ! -s "$HTTP_TRACE" ]]

: > "$HTTP_TRACE"
rm -f "$GET_COUNT_FILE"
PATH="$TMP_DIR/bin:$PATH" \
  HOMEPAGE_REVALIDATE_SECRET="0123456789abcdef0123456789abcdef" \
  HOMEPAGE_REFRESH_BASE_URL="https://www.aivizens.test" \
  "$REFRESH" "$TEST_DATE"
grep -q 'POST .*https://www.aivizens.test/api/internal/revalidate-homepage' "$HTTP_TRACE"
[[ "$(grep -c 'https://www.aivizens.test/$' "$HTTP_TRACE")" == "2" ]]

: > "$HTTP_TRACE"
rm -f "$GET_COUNT_FILE"
if PATH="$TMP_DIR/bin:$PATH" \
  HOMEPAGE_REVALIDATE_SECRET="0123456789abcdef0123456789abcdef" \
  HOMEPAGE_REFRESH_BASE_URL="https://www.aivizens.test" \
  FAKE_HOMEPAGE_ALWAYS_STALE=1 \
  "$REFRESH" "$TEST_DATE"; then
  echo "refresh unexpectedly accepted a stale homepage" >&2
  exit 1
fi
[[ "$(grep -c 'https://www.aivizens.test/$' "$HTTP_TRACE")" == "3" ]]

: > "$HTTP_TRACE"
: > "$TMP_DIR/command-trace"
rm -f "$GET_COUNT_FILE"
TRACE_FILE="$TMP_DIR/command-trace" PATH="$TMP_DIR/bin:$PATH" \
  PROJECT_ROOT="$TMP_DIR/project" AIVIZENS_OPERATOR_ID="test-operator" \
  HOMEPAGE_REVALIDATE_SECRET="0123456789abcdef0123456789abcdef" \
  HOMEPAGE_REFRESH_BASE_URL="https://www.aivizens.test" \
  FAKE_REVALIDATE_FAIL=1 \
  bash "$RUNNER"
grep -q 'POST .*https://www.aivizens.test/api/internal/revalidate-homepage' "$HTTP_TRACE"
grep -q 'python -m ai_brief deliver --date .* --retry-transient' "$TMP_DIR/command-trace"

echo "homepage refresh contract ok"
