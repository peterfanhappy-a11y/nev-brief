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
grep -q '<integer>6</integer>' "$GEN"
grep -q '<integer>45</integer>' "$GEN"
grep -q '<string>com.aivizens.ai-release</string>' "$REL"
grep -q '<integer>8</integer>' "$REL"
grep -q '<integer>0</integer>' "$REL"
grep -q 'ai-generate-.*\.log' "$GEN_RUN"
grep -q 'ai-release-.*\.log' "$REL_RUN"
grep -q 'python -m ai_brief generate' "$GEN_RUN"
grep -q 'python -m ai_brief release' "$REL_RUN"
if grep -R -n -- 'python -m ai_brief daily' "$GEN_RUN" "$REL_RUN"; then
  echo 'retired daily command found' >&2
  exit 1
fi

echo 'launchd schedule contract ok'
