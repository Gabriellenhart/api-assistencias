#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ ! -d .venv ]]; then
  echo "[dev run] ERRO: .venv nao encontrado. Rode ./scripts/dev/bootstrap.sh primeiro." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export FLASK_APP="${FLASK_APP:-run.py}"
export FLASK_ENV="${FLASK_ENV:-development}"
export FLASK_DEBUG="${FLASK_DEBUG:-1}"

HOST="${FLASK_RUN_HOST:-127.0.0.1}"
PORT="${FLASK_RUN_PORT:-5000}"

echo "[dev run] iniciando API em http://${HOST}:${PORT}"
exec python -m flask run --host "${HOST}" --port "${PORT}" --debug
