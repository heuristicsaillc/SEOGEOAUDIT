#!/usr/bin/env bash
# Start SEO GEO Auditor with one command (UI + API on http://127.0.0.1:8000).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d node_modules ]]; then
  echo "Installing root dependencies..."
  npm install
fi

echo ""
echo "SEO GEO Auditor"
echo "  App: http://127.0.0.1:8000"
echo "  API: http://127.0.0.1:8000/docs"
echo "Press Ctrl+C to stop."
echo ""

exec npm run dev
