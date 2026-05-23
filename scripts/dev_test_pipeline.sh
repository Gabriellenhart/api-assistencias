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
export FLASK_ENV=testing

if [[ -z "${TEST_DATABASE_URI:-}" ]]; then
  echo "[ERRO] TEST_DATABASE_URI nao definido."
  exit 1
fi

pytest -q
