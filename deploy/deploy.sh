#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env.production}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.production.yml)

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE does not exist. Copy .env.production.example and fill in the real secrets."
  exit 1
fi

if grep -Eq 'REPLACE_WITH|change-this|development-secret' "$ENV_FILE"; then
  echo "ERROR: $ENV_FILE still contains placeholder credentials."
  exit 1
fi

command -v docker >/dev/null || { echo "ERROR: Docker is not installed."; exit 1; }
docker compose version >/dev/null || { echo "ERROR: Docker Compose is unavailable."; exit 1; }

printf '\n[1/6] Validating Compose configuration...\n'
"${COMPOSE[@]}" config --quiet

printf '\n[2/6] Building production images...\n'
"${COMPOSE[@]}" build --pull

printf '\n[3/6] Running production preflight...\n'
"${COMPOSE[@]}" run --rm --no-deps api python scripts/production_preflight.py

printf '\n[4/6] Starting database, API, worker, backup, and frontend...\n'
"${COMPOSE[@]}" up -d --remove-orphans

printf '\n[5/6] Waiting for application health...\n'
for attempt in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8800/api/v1/ready >/dev/null && curl -fsS http://127.0.0.1:3300/login >/dev/null; then
    break
  fi
  if [[ "$attempt" == "40" ]]; then
    echo "ERROR: Application did not become healthy."
    "${COMPOSE[@]}" ps
    "${COMPOSE[@]}" logs --tail=150 api web
    exit 1
  fi
  sleep 3
done

printf '\n[6/6] Deployment status...\n'
"${COMPOSE[@]}" ps

cat <<'EOF'

Local deployment checks passed:
  Frontend: http://127.0.0.1:3300
  API:      http://127.0.0.1:8800/api/v1/ready

The public site will work after inventory.hiddenoasis.app points to this server and the reverse proxy/SSL configuration is enabled.
EOF
