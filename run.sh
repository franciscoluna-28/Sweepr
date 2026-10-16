#!/usr/bin/env bash
# Sweepr launcher for macOS/Linux.
#   ./run.sh        build the UI if needed, then start the app (opens browser)
#   ./run.sh --dev  API with auto-reload + Vite dev server (HMR)
set -euo pipefail

cd "$(dirname "$0")"
export SWEEPR_PORT="${SWEEPR_PORT:-8765}"
PY=".venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "No virtualenv found at $PY. See README.md (\"Setup\") first." >&2
  exit 1
fi

if [[ "${1:-}" == "--dev" ]]; then
  "$PY" -m uvicorn app.main:app --reload --port "$SWEEPR_PORT" &
  API_PID=$!
  trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
  echo "API on http://127.0.0.1:$SWEEPR_PORT — UI (HMR) on http://127.0.0.1:5173"
  pnpm --dir app/ui dev --open
else
  if [[ ! -f app/ui/dist/index.html ]]; then
    echo "Building UI ..."
    pnpm --dir app/ui install
    pnpm --dir app/ui build
  fi
  echo "Starting Sweepr on http://127.0.0.1:$SWEEPR_PORT ..."
  exec "$PY" start.py
fi
