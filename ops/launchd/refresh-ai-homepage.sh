#!/usr/bin/env bash
set -euo pipefail

RUN_DATE="${1:-}"
if [[ ! "$RUN_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "homepage refresh requires YYYY-MM-DD" >&2
    exit 2
fi

SECRET="${HOMEPAGE_REVALIDATE_SECRET:-}"
if [[ "${#SECRET}" -lt 32 ]]; then
    echo "homepage refresh skipped: HOMEPAGE_REVALIDATE_SECRET must contain at least 32 characters" >&2
    exit 1
fi

BASE_URL="${HOMEPAGE_REFRESH_BASE_URL:-https://www.aivizens.com}"
BASE_URL="${BASE_URL%/}"

curl --fail-with-body --silent --show-error --request POST \
    --header "Authorization: Bearer $SECRET" \
    --header "Content-Type: application/json" \
    --data "{\"briefDate\":\"$RUN_DATE\"}" \
    "$BASE_URL/api/internal/revalidate-homepage" >/dev/null

for attempt in 1 2 3; do
    homepage=""
    if homepage="$(curl --fail --silent --show-error "$BASE_URL/")" \
        && [[ "$homepage" == *"/daily/$RUN_DATE"* ]]; then
        echo "homepage refresh verified date=$RUN_DATE attempt=$attempt"
        exit 0
    fi
    [[ "$attempt" -eq 3 ]] || sleep 1
done

echo "homepage refresh failed: $BASE_URL/ does not contain /daily/$RUN_DATE" >&2
exit 1
