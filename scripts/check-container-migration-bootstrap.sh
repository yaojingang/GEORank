#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export POSTGRES_PASSWORD=test-contract-password
export GEORANK_ENV_FILE=/dev/null
compose_file="$repo_root/docker-compose.yml"
contract_override="$repo_root/docker-compose.migration-contract.yml"
project="georank-migration-contract-${GITHUB_RUN_ID:-local}-$$"
compose=(docker compose -f "$compose_file" -f "$contract_override" -p "$project")

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  docker image rm "${project}-api" "${project}-migrate" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "EFFECTIVE_PRODUCTION_COMPOSE: validate the merged production service graph"
"${compose[@]}" config --format json | python3 -c '
import json, sys
config = json.load(sys.stdin)
services = config["services"]
required = {"traefik", "frontend", "api", "worker", "beat", "crawler", "migrate", "postgres", "redis", "qdrant", "neo4j"}
assert required.issubset(services)
assert services["migrate"]["command"] == ["python", "-m", "app.scripts.migrate"]
assert set(services["migrate"]["environment"]) == {
    "DEBUG", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"
}
assert services["api"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
for service_name in ("traefik", "frontend", "api"):
    assert "georank-net" in services[service_name]["networks"]
for service_name in ("traefik", "frontend"):
    assert services[service_name]["ports"] == [{
        "mode": "ingress", "host_ip": "127.0.0.1", "target": 80,
        "published": "0", "protocol": "tcp"
    }]
for service_name in ("api", "postgres", "redis", "qdrant", "neo4j", "minio"):
    assert not services[service_name].get("ports")
assert not services["api"].get("volumes")
assert all(
    volume.get("source") != "/var/run/docker.sock"
    for volume in services["traefik"].get("volumes", [])
)
traefik_config_mount = next(
    volume for volume in services["traefik"]["volumes"]
    if volume["target"] == "/etc/traefik"
)
assert traefik_config_mount["read_only"] is True
'

echo "FRESH_DATABASE: build the production API image and migrate an empty database"
"${compose[@]}" build api migrate
"${compose[@]}" up -d --wait postgres

echo "DIRECT_ENTRYPOINT_FAIL_CLOSED: application image rejects an empty database"
set +e
direct_output=$("${compose[@]}" run --rm --no-deps api 2>&1)
direct_code=$?
set -e
test "$direct_code" -ne 0
printf '%s\n' "$direct_output" | grep -q \
  "database has no alembic_version; run the migration service"

echo "CONCURRENT_EMPTY_DATABASE: serialize two migration processes with the advisory lock"
"${compose[@]}" run --rm migrate &
first_migration=$!
"${compose[@]}" run --rm migrate &
second_migration=$!
wait "$first_migration"
wait "$second_migration"

"${compose[@]}" up -d --wait api
fresh_state=$(
  "${compose[@]}" exec -T postgres \
    psql -U georank -d georank_contract -Atc \
    "SELECT (SELECT string_agg(version_num, ',') FROM alembic_version), (SELECT count(*) FROM expert_profiles);"
)
test "$fresh_state" = "016_merge_platform_iterations|5"
"${compose[@]}" exec -T api curl --fail --silent http://localhost:8000/api/health >/dev/null
expert_count=$(
  "${compose[@]}" exec -T api \
    python -c 'import json,urllib.request; data=json.load(urllib.request.urlopen("http://localhost:8000/api/experts")); print(len(data["items"]))'
)
test "$expert_count" = "5"

echo "PRODUCTION_GATEWAY: exercise file-provider routes on the shared Compose network"
"${compose[@]}" up -d --wait traefik frontend
gateway_port=$("${compose[@]}" port traefik 80 | awk -F: '{print $NF}')
frontend_port=$("${compose[@]}" port frontend 80 | awk -F: '{print $NF}')
gateway="http://127.0.0.1:$gateway_port"
direct_frontend="http://127.0.0.1:$frontend_port"
attempt=0
until curl --fail --silent "$gateway/api/health" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if test "$attempt" -ge 30; then
    echo "gateway did not become ready within 30 seconds" >&2
    exit 1
  fi
  sleep 1
done
for iteration in $(seq 1 40); do
  curl --fail --silent "$gateway/" >/dev/null
  curl --fail --silent "$gateway/api/health" >/dev/null
done
curl --fail --silent "$gateway/" >/dev/null
curl --fail --silent "$gateway/api/health" >/dev/null
curl --fail --silent "$gateway/api/companies/" >/dev/null
curl --fail --silent "$gateway/tutorial" >/dev/null
curl --fail --silent "$gateway/experts" >/dev/null
curl --fail --silent "$gateway/admin/login" >/dev/null
curl --fail --silent "$gateway/apix" >/dev/null
curl --fail --silent "$direct_frontend/" >/dev/null
gateway_expert_count=$(
  curl --fail --silent "$gateway/api/experts" |
    python3 -c 'import json,sys; print(len(json.load(sys.stdin)["items"]))'
)
test "$gateway_expert_count" = "5"

traefik_logs=$("${compose[@]}" logs --no-color traefik 2>&1)
if printf '%s\n' "$traefik_logs" |
  grep -Eiq 'failed to retrieve information|provider.*error|status.?code.?502| 502 '; then
  printf '%s\n' "$traefik_logs"
  exit 1
fi
printf '%s\n' "$traefik_logs" | grep -Eq 'GET /apix.*frontend@file'

echo "IDEMPOTENT_RESTART: rerun the one-shot migrator at head"
"${compose[@]}" run --rm migrate
restart_state=$(
  "${compose[@]}" exec -T postgres \
    psql -U georank -d georank_contract -Atc \
    "SELECT (SELECT string_agg(version_num, ',') FROM alembic_version), (SELECT count(*) FROM expert_profiles);"
)
test "$restart_state" = "$fresh_state"

echo "LEGACY_FAIL_CLOSED: preserve a managed schema with no Alembic ownership"
"${compose[@]}" stop api >/dev/null
"${compose[@]}" exec -T postgres \
  psql -U georank -d georank_contract -v ON_ERROR_STOP=1 -c \
  "DROP SCHEMA public CASCADE; CREATE SCHEMA public; CREATE TABLE users(id uuid PRIMARY KEY);" \
  >/dev/null
"${compose[@]}" rm -sf migrate api >/dev/null

echo "MIGRATION_FAILURE_BLOCKS_API: Compose must keep API stopped when migration fails"
set +e
failure_output=$("${compose[@]}" up -d api 2>&1)
failure_code=$?
set -e
test "$failure_code" -ne 0
printf '%s\n' "$failure_output" | grep -q "didn't complete successfully: exit 1"
migration_logs=$("${compose[@]}" logs --no-color migrate 2>&1)
printf '%s\n' "$migration_logs" | grep -q \
  "managed tables exist without alembic_version"

api_container=$("${compose[@]}" ps -aq api)
if test -n "$api_container"; then
  test "$(docker inspect -f '{{.State.Running}}' "$api_container")" = "false"
fi

legacy_state=$(
  "${compose[@]}" exec -T postgres \
    psql -U georank -d georank_contract -Atc \
    "SELECT to_regclass('public.users') IS NOT NULL, to_regclass('public.alembic_version') IS NULL;"
)
test "$legacy_state" = "t|t"

echo "Container migration bootstrap contract passed"
