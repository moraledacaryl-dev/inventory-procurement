#!/usr/bin/env sh
set -eu
(cd backend && python -m compileall -q app tests scripts && pytest)
(cd frontend && npm run lint && npm run typecheck && npm run build)
