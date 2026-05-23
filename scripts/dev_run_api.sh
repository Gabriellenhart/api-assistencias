#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ -d venv ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -d venv_api ]]; then
  # shellcheck disable=SC1091
  source venv_api/bin/activate
else
  echo "[ERRO] Nenhum virtualenv encontrado (venv ou venv_api)."
  exit 1
fi

export FLASK_APP=run.py
export FLASK_ENV="${FLASK_ENV:-development}"
export FLASK_DEBUG="${FLASK_DEBUG:-1}"

WORKERS="${GUNICORN_WORKERS:-2}"
BIND_ADDR="${GUNICORN_BIND:-127.0.0.1:5000}"

exec gunicorn \
  --bind "${BIND_ADDR}" \
  --workers "${WORKERS}" \
  --timeout 120 \
  --reload \
  run:app
