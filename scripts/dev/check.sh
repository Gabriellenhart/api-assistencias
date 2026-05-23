#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export FLASK_APP="${FLASK_APP:-run.py}"
export FLASK_ENV="${FLASK_ENV:-development}"
export SECRET_KEY="${SECRET_KEY:-dev-secret}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-dev-jwt-secret}"
export DEV_DATABASE_URI="${DEV_DATABASE_URI:-postgresql://assistencias:assistencias@localhost:5432/assistencias_dev}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000}"

echo "[dev check] importando aplicacao"
python -c "from api import create_app; app = create_app('development'); print(app.name)"

echo "[dev check] validando sintaxe"
python -m compileall api scraper scripts config.py run.py

if python -m pytest --version >/dev/null 2>&1; then
  echo "[dev check] rodando pytest"
  python -m pytest
else
  echo "[dev check] pytest nao instalado; pulando testes"
fi

if [[ -n "${DEV_DATABASE_URI:-${DATABASE_URI:-}}" ]]; then
  echo "[dev check] verificando estado das migrations"
  DB_CURRENT_LOG="$(mktemp)"
  if ! python -m flask db current >"${DB_CURRENT_LOG}" 2>&1; then
    echo "[dev check] aviso: nao foi possivel consultar flask db current. Verifique PostgreSQL e .env." >&2
    rm -f "${DB_CURRENT_LOG}"
  else
    cat "${DB_CURRENT_LOG}"
    rm -f "${DB_CURRENT_LOG}"
  fi
fi

echo "[dev check] OK"
