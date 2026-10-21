#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/inventory-procurement-online
BACKEND_ENV=/etc/hiddenoasis/inventory-backend.env
FRONTEND_ENV=/etc/hiddenoasis/inventory-frontend.env
CERT_DIR=/etc/letsencrypt/live/inventory.hiddenoasis.app
NPM_CACHE=/var/cache/hiddenoasis/inventory-npm

wait_for_url() {
  local url="$1"
  local host_header="${2:-}"
  local attempts=30
  local delay=1

  for ((i=1; i<=attempts; i++)); do
    if [[ -n "$host_header" ]]; then
      if curl -fsS -H "Host: $host_header" "$url" >/dev/null; then return 0; fi
    elif curl -fsS "$url" >/dev/null; then
      return 0
    fi
    sleep "$delay"
  done

  echo "Service did not become ready: $url" >&2
  return 1
}

[[ $EUID -eq 0 ]] || { echo "Run as root."; exit 1; }
[[ -d "$APP_DIR/.git" ]] || { echo "Missing repository at $APP_DIR"; exit 1; }
[[ -f "$BACKEND_ENV" ]] || { echo "Missing $BACKEND_ENV"; exit 1; }
[[ -f "$FRONTEND_ENV" ]] || { echo "Missing $FRONTEND_ENV"; exit 1; }
[[ -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]] || { echo "Missing TLS certificate for inventory.hiddenoasis.app. Run certbot before deployment."; exit 1; }

# Fail *before backup, build or migration* if bash sourcing silently corrupts
# the JSON destinations. Workers cannot reach Accounting without this map.
(
  set -a
  source "$BACKEND_ENV"
  set +a
  python3 - <<'PY'
import json, os
raw = os.environ.get("INTEGRATION_ENDPOINTS_JSON", "{}")
try:
    routes = json.loads(raw)
except (ValueError, TypeError) as exc:
    raise SystemExit("Inventory integration endpoints are not valid JSON after sourcing the environment file") from exc
if not isinstance(routes, dict):
    raise SystemExit("Inventory integration endpoints must be a JSON object")
if os.environ.get("INTEGRATION_API_KEY") and not routes.get("accounting"):
    raise SystemExit("Accounting integration key is configured, but the Accounting destination is missing")
print("INVENTORY INTEGRATION ENVIRONMENT: PASS")
PY
)

# Back up the existing production database before any dependency installation,
# frontend build, migration, or service restart. Never silently deploy if the
# backup cannot be read back and validated.
BACKUP_ROOT=/var/backups/hiddenoasis/inventory
BACKUP_DB=hiddenoasis_inventory_live
install -d -m 0700 "$BACKUP_ROOT/releases"
install -d -o hiddenoasis -g hiddenoasis "$BACKUP_ROOT" "$NPM_CACHE"
command -v pg_dump >/dev/null || { echo "pg_dump is required for safe deployment." >&2; exit 1; }
command -v pg_restore >/dev/null || { echo "pg_restore is required for backup validation." >&2; exit 1; }
command -v flock >/dev/null || { echo "flock is required for deployment serialization." >&2; exit 1; }
exec 9>/run/lock/hiddenoasis-inventory-deploy.lock
flock -n 9 || { echo "Another Inventory deployment is running." >&2; exit 1; }
free_bytes="$(df -B1 --output=avail "$BACKUP_ROOT" | tail -n 1 | tr -d '[:space:]')"
if (( free_bytes < 2147483648 )); then
  echo "Inventory deployment blocked: less than 2 GiB available for backup and build." >&2
  exit 1
fi
pg_isready -h 127.0.0.1 -p 5432 >/dev/null
if [[ "$(sudo -u postgres psql -d postgres -Atqc 'SELECT pg_is_in_recovery()')" != "f" ]]; then
  echo "Inventory deployment blocked: PostgreSQL is not the writable primary." >&2
  exit 1
fi
backup_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$BACKUP_ROOT/releases/inventory-predeploy-${backup_stamp}-${BASHPID}.dump"
umask 077
sudo -u postgres pg_dump -Fc -d "$BACKUP_DB" > "$backup_file.tmp"
test -s "$backup_file.tmp" || { echo "Inventory backup is empty." >&2; exit 1; }
pg_restore --list "$backup_file.tmp" >/dev/null
mv "$backup_file.tmp" "$backup_file"
backup_checksum="$(sha256sum "$backup_file" | cut -d' ' -f1)"
[[ "$backup_checksum" =~ ^[0-9a-f]{64}$ ]] || { echo "Backup checksum invalid." >&2; exit 1; }
echo "INVENTORY BACKUP VERIFIED: $backup_file SHA256=$backup_checksum"


python3 -m venv "$APP_DIR/backend/.venv"
"$APP_DIR/backend/.venv/bin/pip" install --upgrade pip
"$APP_DIR/backend/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

# Keep Git-owned frontend source unchanged after deployment. Next.js updates
# next-env.d.ts during builds, so temporarily make that generated declaration
# writable by the build account and restore its committed contents afterwards.
rm -rf "$APP_DIR/frontend/node_modules" "$APP_DIR/frontend/.next"
install -d -o hiddenoasis -g hiddenoasis "$APP_DIR/frontend/node_modules" "$APP_DIR/frontend/.next"
chown hiddenoasis:hiddenoasis "$APP_DIR/frontend/next-env.d.ts"
sudo -u hiddenoasis env HOME=/tmp NPM_CONFIG_CACHE="$NPM_CACHE" bash -c "cd '$APP_DIR/frontend' && set -a && source '$FRONTEND_ENV' && set +a && npm ci --include=dev && npm run build && mkdir -p .next/standalone/.next && rm -rf .next/standalone/.next/static && cp -a .next/static .next/standalone/.next/static && if [ -d public ]; then rm -rf .next/standalone/public && cp -a public .next/standalone/public; fi"
git -C "$APP_DIR" restore -- frontend/next-env.d.ts

# Apply schema changes before account bootstrap. The backend environment is a
# protected root-readable production secret file, so source it while this
# root-only deployment script is still privileged instead of weakening its
# filesystem permissions for the runtime account.
bash -c "cd '$APP_DIR/backend' && set -a && source '$BACKEND_ENV' && set +a && .venv/bin/python scripts/production_preflight.py && .venv/bin/alembic upgrade head && if [[ -n \"\${OWNER_EMAIL:-}\" && -n \"\${OWNER_PASSWORD:-}\" ]]; then .venv/bin/python scripts/ensure_owner.py --non-interactive; else echo 'OWNER_EMAIL/OWNER_PASSWORD not set; owner bootstrap skipped.'; fi"

install -m 0644 "$APP_DIR/deploy/systemd/hiddenoasis-inventory-backend.service" /etc/systemd/system/
install -m 0644 "$APP_DIR/deploy/systemd/hiddenoasis-inventory-frontend.service" /etc/systemd/system/
install -m 0644 "$APP_DIR/deploy/systemd/hiddenoasis-inventory-worker.service" /etc/systemd/system/
install -m 0644 "$APP_DIR/deploy/systemd/hiddenoasis-inventory-backup.service" /etc/systemd/system/
install -m 0644 "$APP_DIR/deploy/systemd/hiddenoasis-inventory-backup.timer" /etc/systemd/system/
install -m 0644 "$APP_DIR/deploy/nginx/inventory-hiddenoasis.conf" /etc/nginx/sites-available/inventory-hiddenoasis
ln -sfn /etc/nginx/sites-available/inventory-hiddenoasis /etc/nginx/sites-enabled/inventory-hiddenoasis

systemctl daemon-reload
systemctl enable hiddenoasis-inventory-backend.service hiddenoasis-inventory-frontend.service hiddenoasis-inventory-worker.service hiddenoasis-inventory-backup.timer
systemctl restart hiddenoasis-inventory-backend.service hiddenoasis-inventory-frontend.service hiddenoasis-inventory-worker.service
systemctl start hiddenoasis-inventory-backup.timer
nginx -t
systemctl reload nginx

wait_for_url http://127.0.0.1:8300/api/v1/ready inventory.hiddenoasis.app
wait_for_url http://127.0.0.1:3300/login
wait_for_url https://inventory.hiddenoasis.app/login
systemctl --no-pager --full status hiddenoasis-inventory-backend.service hiddenoasis-inventory-frontend.service hiddenoasis-inventory-worker.service

# Mark only a fully verified release as active.
if [[ -d "$APP_DIR/.git" ]]; then
  release_sha="$(git -C "$APP_DIR" rev-parse HEAD)"
  echo "INVENTORY DEPLOYMENT GATE: PASS | $release_sha | backup $backup_file | sha256 $backup_checksum"
fi
