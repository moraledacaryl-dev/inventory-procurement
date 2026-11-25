#!/usr/bin/env bash
set -euo pipefail
training_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$training_root/frontend"
NEXT_PUBLIC_INVENTORY_TRAINING=1 NEXT_TELEMETRY_DISABLED=1 npm run build
node "$training_root/scripts/verify-training-web.mjs"
mkdir -p .next/standalone/.next
cp -R .next/static .next/standalone/.next/
if [[ -d public ]]; then cp -R public .next/standalone/; fi
cd "$training_root"
python3 - <<'PY'
from pathlib import Path
roots = [Path('frontend/.next/standalone')]
bad = [str(p) for root in roots for p in root.rglob('*') if p.is_file() and
       (p.name.startswith('.env') or p.suffix in {'.sqlite','.db'} or p.name in {'session-key','manager-key'})]
if bad: raise SystemExit('Refusing private state in package: ' + ', '.join(bad))
PY
printf '%s\n' 'Standalone training web build prepared. Install the Python runtime separately; see docs/training/INSTALLATION.md.'
