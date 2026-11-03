#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ "${1:-}" != "--native" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    printf '%s\n' 'Install Docker Desktop or use ./run_demo.sh --native (requires uv and Node.js 24).'
    exit 1
  fi
  exec docker compose up --build
fi
command -v uv >/dev/null 2>&1 || { printf '%s\n' 'uv is required: https://docs.astral.sh/uv/'; exit 1; }
command -v npm >/dev/null 2>&1 || { printf '%s\n' 'Node.js 24 LTS is required: https://nodejs.org/'; exit 1; }
cd backend
[ -x .venv/bin/python ] || uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.lock
cd ..
npm ci --no-audit --no-fund
exec backend/.venv/bin/python scripts/native_demo.py
