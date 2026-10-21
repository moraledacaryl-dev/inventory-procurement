#!/usr/bin/env bash
# Deploy the exact certified Inventory commit on the native production server.
# Run as root with an explicit 40-character main-branch release SHA.
set -euo pipefail

APP_DIR=/opt/inventory-procurement-online
TARGET_SHA="${1:-}"
[[ "${EUID}" -eq 0 ]] || { echo "Native deployment must run as root." >&2; exit 1; }
[[ "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Expected a 40-character release SHA." >&2; exit 1; }
[[ -d "$APP_DIR/.git" ]] || { echo "Missing live Inventory git checkout." >&2; exit 1; }
[[ -f "$APP_DIR/deploy/install-native.sh" ]] || { echo "Missing installer." >&2; exit 1; }
[[ -z "$(git -C "$APP_DIR" status --porcelain --untracked-files=no)" ]] || {
  echo "Tracked production checkout changes detected. Refusing destructive checkout." >&2
  exit 1
}

git -C "$APP_DIR" fetch --no-tags origin main
main_sha="$(git -C "$APP_DIR" rev-parse origin/main)"
[[ "$main_sha" == "$TARGET_SHA" ]] || {
  echo "Release target is no longer the exact main HEAD: requested=$TARGET_SHA main=$main_sha" >&2
  exit 1
}
git -C "$APP_DIR" cat-file -e "$TARGET_SHA^{commit}"
previous_sha="$(git -C "$APP_DIR" rev-parse HEAD)"
echo "Inventory deploying $TARGET_SHA (previous $previous_sha)"

# The installer acquires the exclusive deployment lock and performs a verified
# PostgreSQL backup *before* package changes, migration and service restarts.
git -C "$APP_DIR" checkout --detach "$TARGET_SHA"
if ! bash "$APP_DIR/deploy/install-native.sh"; then
  echo "INVENTORY DEPLOYMENT GATE: FAIL | target $TARGET_SHA | previous $previous_sha" >&2
  echo "Do not attempt an automatic database downgrade. Retain predeploy backup and investigate." >&2
  exit 1
fi
[[ "$(git -C "$APP_DIR" rev-parse HEAD)" == "$TARGET_SHA" ]] || {
  echo "Checkout changed during deployment" >&2
  exit 1
}
echo "INVENTORY RELEASE VERIFIED: $TARGET_SHA"
