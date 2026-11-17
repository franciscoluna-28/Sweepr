#!/usr/bin/env sh
# Run the Sweepr backend and the Vite dev server together.
set -eu
cd "$(dirname "$0")/.."
exec uv run python scripts/dev.py "$@"
