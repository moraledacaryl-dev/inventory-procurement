#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/inventory-procurement-online
BACKEND_ENV=/etc/hiddenoasis/inventory-backend.env
FRONTEND_ENV=/etc/hiddenoasis/inventory-frontend.env

wait_for_url() {
  local url="$1"
  local host_header="${2:-}"
  local attempts=30
  local delay=1

  for ((i=1; i<=attempts; i++)); do
    if [[ -n "$host_header" ]]; then
      if curl -fsS -H "Host: $host_header" "$url" >/dev/null; then
        return 0
      fi
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

install -d -o hiddenoasis -g hiddenoasis /var/backups/hiddenoasis/inventory
python3 -m venv "$APP_DIR/backend/.venv"
"$APP_DIR/backend/.venv/bin/pip" install --upgrade pip
"$APP_DIR/backend/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

sudo -H -u hiddenoasis bash -lc "cd '$APP_DIR/frontend' && set -a && source '$FRONTEND_ENV' && set +a && npm install && npm run build && mkdir -p .next/standalone/.next && rm -rf .next/standalone/.next/static && cp -a .next/static .next/standalone/.next/static && if [ -d public ]; then rm -rf .next/standalone/public && cp -a public .next/standalone/public; fi"

install -m 0644 "$APP_DIR/deploy/systemd/hiddenoasis-inventory-backend.service" /etc/systemd/system/
install -m 0644 "$APP_DIR/deploy/systemd/hiddenoasis-inventory-frontend.service" /etc/systemd/system/
install -m 0644 "$APP_DIR/deploy/systemd/hiddenoasis-inventory-worker.service" /etc/systemd/system/
install -m 0644 "$APP_DIR/deploy/systemd/hiddenoasis-inventory-backup.service" /etc/systemd/system/
install -m 0644 "$APP_DIR/deploy/systemd/hiddenoasis-inventory-backup.timer" /etc/systemd/system/
install -m 0644 "$APP_DIR/deploy/nginx/inventory-hiddenoasis.conf" /etc/nginx/sites-available/inventory-hiddenoasis
ln -sfn /etc/nginx/sites-available/inventory-hiddenoasis /etc/nginx/sites-enabled/inventory-hiddenoasis

systemctl daemon-reload
systemctl enable --now hiddenoasis-inventory-backend.service
systemctl enable --now hiddenoasis-inventory-frontend.service
systemctl enable --now hiddenoasis-inventory-worker.service
systemctl enable --now hiddenoasis-inventory-backup.timer
nginx -t
systemctl reload nginx

wait_for_url http://127.0.0.1:8300/api/v1/ready inventory.hiddenoasis.app
wait_for_url http://127.0.0.1:3300/login
systemctl --no-pager --full status hiddenoasis-inventory-backend.service hiddenoasis-inventory-frontend.service hiddenoasis-inventory-worker.service
