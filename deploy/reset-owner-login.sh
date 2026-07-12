#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/inventory-procurement-online
BACKEND_ENV=/etc/hiddenoasis/inventory-backend.env

[[ $EUID -eq 0 ]] || { echo "Run as root." >&2; exit 1; }
[[ -d "$APP_DIR/backend" ]] || { echo "Missing backend directory: $APP_DIR/backend" >&2; exit 1; }
[[ -f "$BACKEND_ENV" ]] || { echo "Missing backend environment file: $BACKEND_ENV" >&2; exit 1; }

read -r -p "Owner email: " OWNER_EMAIL
read -r -p "Owner full name [Owner]: " OWNER_NAME
OWNER_NAME=${OWNER_NAME:-Owner}

cd "$APP_DIR/backend"
set -a
source "$BACKEND_ENV"
set +a

sudo -H -u hiddenoasis "$APP_DIR/backend/.venv/bin/python" scripts/reset_owner_password.py \
  --email "$OWNER_EMAIL" \
  --full-name "$OWNER_NAME"

systemctl restart hiddenoasis-inventory-backend.service
sleep 2
curl -fsS http://127.0.0.1:8300/api/v1/ready >/dev/null
echo "Owner login reset successfully."
