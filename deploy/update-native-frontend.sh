#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

echo "[1/5] Install dependencies"
npm ci --include=dev

echo "[2/5] Build standalone frontend"
npm run build

echo "[3/5] Package static assets for standalone server"
test -f .next/standalone/server.js
test -d .next/static
mkdir -p .next/standalone/.next
rm -rf .next/standalone/.next/static
cp -a .next/static .next/standalone/.next/static
if [[ -d public ]]; then
  rm -rf .next/standalone/public
  cp -a public .next/standalone/public
fi

echo "[4/5] Verify standalone assets"
test -d .next/standalone/.next/static/chunks
asset="$(find .next/standalone/.next/static/chunks -maxdepth 1 -name '*.js' -type f -print -quit)"
test -n "$asset" && test -s "$asset"

echo "[5/5] Restart frontend and verify HTTP and static assets"
sudo systemctl restart hiddenoasis-inventory-frontend
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:3300/login >/dev/null; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1:3300/login >/dev/null
relative="${asset#".next/standalone"}"
curl -fsS "http://127.0.0.1:3300${relative}" >/dev/null
curl -fsS "https://inventory.hiddenoasis.app${relative}" >/dev/null
echo "Frontend HTML and standalone JS verified locally and publicly."
