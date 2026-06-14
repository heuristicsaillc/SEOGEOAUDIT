#!/usr/bin/env bash
# Preflight: ensure backend venv and uvicorn exist before starting the API.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ ! -x "$ROOT/backend/.venv/bin/uvicorn" ]]; then
  echo "Missing backend/.venv — run:"
  echo "  cd backend && python3 -m venv .venv && pip install -r requirements.txt"
  exit 1
fi
