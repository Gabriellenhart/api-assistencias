#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${APP_DIR}/scheduler_cron.log"

cd "${APP_DIR}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -d venv ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -d venv_api ]]; then
  # shellcheck disable=SC1091
  source venv_api/bin/activate
else
  echo "[ERRO] Nenhum virtualenv encontrado (venv ou venv_api)." | tee -a "${LOG_FILE}"
  exit 1
fi

{
  echo "=== Iniciando Sync SolarZ: $(date) ==="
  echo ">>> Rodando Sync Usinas..."
  python scraper/solarz_sync_usinas.py
  echo ">>> Rodando Sync Clientes..."
  python scraper/solarz_sync_clientes.py
  echo "=== Fim do Sync: $(date) ==="
  echo "---------------------------------------------------"
} >> "${LOG_FILE}" 2>&1
