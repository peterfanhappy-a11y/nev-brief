#!/usr/bin/env bash
set -euo pipefail

mode="${1:-}"
if [[ "$mode" != "integration" && "$mode" != "e2e" ]]; then
  echo "usage: $0 integration|e2e [test arguments...]" >&2
  exit 2
fi
shift

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
web_dir="$(cd "$script_dir/../.." && pwd -P)"
repo_dir="$(cd "$web_dir/../.." && pwd -P)"
compose_file="$script_dir/docker-compose.yml"
project="nev-phase1-task6-${$}"
fake_resend_pid=""
supabase_rest_proxy_pid=""
migration_list=""

export AIVIZENS_TEST_PG_PORT="${AIVIZENS_TEST_PG_PORT:-55436}"
export AIVIZENS_TEST_REST_PORT="${AIVIZENS_TEST_REST_PORT:-55437}"
export AIVIZENS_TEST_RESEND_PORT="${AIVIZENS_TEST_RESEND_PORT:-55438}"
export AIVIZENS_TEST_WEB_PORT="${AIVIZENS_TEST_WEB_PORT:-55439}"
export AIVIZENS_TEST_POSTGREST_PORT="${AIVIZENS_TEST_POSTGREST_PORT:-55440}"
export DATABASE_URL="postgresql://nev_test:nev_test_only@127.0.0.1:${AIVIZENS_TEST_PG_PORT}/nev_subscription_test"
export SUPABASE_URL="http://127.0.0.1:${AIVIZENS_TEST_REST_PORT}"
export AIVIZENS_TEST_POSTGREST_URL="http://127.0.0.1:${AIVIZENS_TEST_POSTGREST_PORT}"
export AIVIZENS_TEST_JWT_SECRET="integration-test-only-postgrest-jwt-secret-32-bytes"
export SUPABASE_SERVICE_ROLE_KEY="$(
  node "$script_dir/create-service-role-jwt.mjs"
)"
export RESEND_API_KEY="re_integration_test_only"
export RESEND_FROM_EMAIL="test-sender@aivizens.invalid"
export RESEND_BASE_URL="http://127.0.0.1:${AIVIZENS_TEST_RESEND_PORT}"
export WEB_BASE_URL="http://127.0.0.1:${AIVIZENS_TEST_WEB_PORT}"
export SUBSCRIPTION_HASH_SECRET="integration-only-subscription-hash-secret"
export SUBSCRIPTIONS_ENABLED="true"
export NEXT_PUBLIC_TURNSTILE_SITE_KEY="1x00000000000000000000AA"
export TURNSTILE_SECRET_KEY="1x0000000000000000000000000000000AA"
export TURNSTILE_TEST_BYPASS="false"
export PYTHON_BIN="${PYTHON_BIN:-$repo_dir/.venv/bin/python}"

cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [[ -n "$fake_resend_pid" ]]; then
    kill "$fake_resend_pid" 2>/dev/null || true
    wait "$fake_resend_pid" 2>/dev/null || true
  fi
  if [[ -n "$supabase_rest_proxy_pid" ]]; then
    kill "$supabase_rest_proxy_pid" 2>/dev/null || true
    wait "$supabase_rest_proxy_pid" 2>/dev/null || true
  fi
  if [[ -n "$migration_list" ]]; then
    rm -f "$migration_list"
  fi
  docker compose -f "$compose_file" -p "$project" down --volumes --remove-orphans >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT INT TERM

wait_for_url() {
  url="$1"
  name="$2"
  for _ in $(seq 1 60); do
    if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "$name did not become ready: $url" >&2
  return 1
}

postgres_ready() {
  local result
  result="$(
    docker compose -f "$compose_file" -p "$project" exec -T postgres \
      psql -U nev_test -d nev_subscription_test -Atqc 'SELECT 1' 2>/dev/null
  )" || return 1
  [[ "$result" == "1" ]]
}

if [[ "$mode" == "integration" ]]; then
  node --test \
    "$script_dir/create-service-role-jwt.test.mjs" \
    "$script_dir/supabase-rest-proxy.test.mjs"
fi

docker compose -f "$compose_file" -p "$project" up -d postgres

for _ in $(seq 1 60); do
  if postgres_ready; then
    break
  fi
  sleep 1
done
if ! postgres_ready; then
  echo "PostgreSQL did not become ready after 60 seconds" >&2
  echo "PostgreSQL compose status:" >&2
  docker compose -f "$compose_file" -p "$project" ps >&2 || true
  echo "PostgreSQL logs (last 100 lines):" >&2
  docker compose -f "$compose_file" -p "$project" logs \
    --no-color --tail=100 postgres >&2 || true
  exit 1
fi

migration_list="$(mktemp "${TMPDIR:-/tmp}/aivizens-task6-migrations.XXXXXX")"
python3 "$repo_dir/scripts/ci/list_postgres_test_migrations.py" \
  "$repo_dir/infra/supabase/migrations" > "$migration_list"
while IFS= read -r migration; do
  docker compose -f "$compose_file" -p "$project" exec -T postgres \
    psql --quiet -U nev_test -d nev_subscription_test \
      --set=ON_ERROR_STOP=on < "$migration"
done < "$migration_list"
docker compose -f "$compose_file" -p "$project" exec -T postgres \
  psql --quiet -U nev_test -d nev_subscription_test \
    --set=ON_ERROR_STOP=on < \
  "$script_dir/postgrest-grants.sql"
rm -f "$migration_list"
migration_list=""

docker compose -f "$compose_file" -p "$project" up -d postgrest
wait_for_url "$AIVIZENS_TEST_POSTGREST_URL" "PostgREST"

node "$script_dir/supabase-rest-proxy.mjs" &
supabase_rest_proxy_pid=$!
wait_for_url "$SUPABASE_URL/rest/v1/" "Supabase REST test proxy"

node "$script_dir/fake-resend.mjs" &
fake_resend_pid=$!
wait_for_url "$RESEND_BASE_URL/health" "fake Resend"

set +e
if [[ "$mode" == "integration" ]]; then
  export NODE_ENV=test
  export TURNSTILE_TEST_BYPASS=true
  "$repo_dir/node_modules/.bin/vitest" run \
    --config "$web_dir/vitest.integration.config.ts" \
    "$web_dir/test/integration/ai-subscription.integration.test.ts" \
    "$@"
else
  "$repo_dir/node_modules/.bin/playwright" test \
    --config "$web_dir/playwright.config.ts" \
    "$@"
fi
test_status=$?
set -e

if [[ "$test_status" -ne 0 ]]; then
  echo "Acceptance test failed; PostgREST compose status:" >&2
  docker compose -f "$compose_file" -p "$project" ps >&2 || true
  echo "PostgREST logs (last 100 lines):" >&2
  docker compose -f "$compose_file" -p "$project" logs \
    --no-color --tail=100 postgrest >&2 || true
  exit "$test_status"
fi
