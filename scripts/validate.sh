#!/usr/bin/env bash
# DocuMind validation: lint + type-check the backend, build-check the frontend.
# Runs the same way locally and in CI (.github/workflows/ci.yml).
#
# Needs only lightweight tools, NOT the heavy runtime deps (docling, torch, OCR
# models) and NOT a running Ollama:
#   pip install ruff mypy          # Python lint + type-check
#   Node.js 20 + npm               # frontend build check
#
# Env:
#   SKIP_FRONTEND=1   skip the frontend build check (e.g. no Node installed)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

step() { printf '\n==> %s\n' "$*"; }

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: '$1' not found. $2" >&2
    exit 1
  fi
}

need ruff "Install it with: pip install ruff mypy"
need mypy "Install it with: pip install ruff mypy"

step "ruff (lint): backend + scripts"
ruff check .

step "mypy (type-check): backend"
(cd backend && mypy --config-file ../mypy.ini app main.py)

if [[ "${SKIP_FRONTEND:-0}" == "1" ]]; then
  step "frontend: skipped (SKIP_FRONTEND=1)"
else
  need npm "Install Node.js 20, or set SKIP_FRONTEND=1."
  step "frontend: install + production build (vite)"
  (
    cd frontend
    if [[ ! -d node_modules ]]; then
      npm ci --no-audit --no-fund
    fi
    npm run build
  )
fi

step "All checks passed."
