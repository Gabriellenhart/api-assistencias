#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-venv}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_ADMIN_USER="${DB_ADMIN_USER:-postgres}"
DB_ADMIN_DB="${DB_ADMIN_DB:-postgres}"
DEV_DB_USER="${DEV_DB_USER:-assistencias_dev}"
DEV_DB_PASS="${DEV_DB_PASS:-assistencias_dev}"
DEV_DB_NAME="${DEV_DB_NAME:-assistencias_dev}"
TEST_DB_USER="${TEST_DB_USER:-assistencias_test}"
TEST_DB_PASS="${TEST_DB_PASS:-assistencias_test}"
TEST_DB_NAME="${TEST_DB_NAME:-assistencias_test}"

echo "[1/6] Instalando dependencias de sistema..."
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  python3 python3-venv python3-dev \
  libpq-dev postgresql postgresql-contrib \
  curl git

echo "[2/6] Inicializando PostgreSQL..."
sudo service postgresql start

echo "[3/6] Criando usuarios e bancos de desenvolvimento/teste..."
sudo -u postgres psql -d "${DB_ADMIN_DB}" -v ON_ERROR_STOP=1 <<SQL
DO \
\$\$ BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DEV_DB_USER}') THEN
      CREATE ROLE ${DEV_DB_USER} LOGIN PASSWORD '${DEV_DB_PASS}';
   END IF;
END \
\$\$;
DO \
\$\$ BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_database WHERE datname = '${DEV_DB_NAME}') THEN
      CREATE DATABASE ${DEV_DB_NAME} OWNER ${DEV_DB_USER};
   END IF;
END \
\$\$;
DO \
\$\$ BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${TEST_DB_USER}') THEN
      CREATE ROLE ${TEST_DB_USER} LOGIN PASSWORD '${TEST_DB_PASS}';
   END IF;
END \
\$\$;
DO \
\$\$ BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_database WHERE datname = '${TEST_DB_NAME}') THEN
      CREATE DATABASE ${TEST_DB_NAME} OWNER ${TEST_DB_USER};
   END IF;
END \
\$\$;
SQL

echo "[4/6] Criando ambiente virtual em ${VENV_DIR}..."
if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "[5/6] Preparando .env..."
if [[ ! -f .env ]]; then
  cp .env.example .env
fi

python - <<PY
from pathlib import Path

env_path = Path('.env')
text = env_path.read_text(encoding='utf-8')
updates = {
    'FLASK_ENV': 'development',
    'FLASK_DEBUG': '1',
    'DEV_DATABASE_URI': 'postgresql://${DEV_DB_USER}:${DEV_DB_PASS}@${DB_HOST}:${DB_PORT}/${DEV_DB_NAME}',
    'TEST_DATABASE_URI': 'postgresql://${TEST_DB_USER}:${TEST_DB_PASS}@${DB_HOST}:${DB_PORT}/${TEST_DB_NAME}',
}
lines = text.splitlines()
current = {}
for line in lines:
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        current[k.strip()] = v
for k, v in updates.items():
    current[k] = v
ordered = []
for k in sorted(current.keys()):
    ordered.append(f"{k}={current[k]}")
env_path.write_text('\n'.join(ordered) + '\n', encoding='utf-8')
PY

echo "[6/6] Aplicando migrations no banco DEV..."
export FLASK_APP=run.py
export FLASK_ENV=development
flask db upgrade

echo "Bootstrap WSL concluido."
echo "Rode: scripts/dev_run_api.sh"
