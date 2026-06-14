#!/usr/bin/env bash
# Start the FastAPI backend (same uvicorn command as before; audit/PDF logic unchanged).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl}"

"$ROOT/scripts/check-backend.sh"

cd "$ROOT/backend"

if [[ "${1:-}" == "--no-reload" ]]; then
  shift
  exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
fi

exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload "$@"
