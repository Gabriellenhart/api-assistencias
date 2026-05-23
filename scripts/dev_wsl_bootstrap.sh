#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_ADMIN_DB="${DB_ADMIN_DB:-postgres}"

DEV_DB_USER="${DEV_DB_USER:-assistencias_dev}"
DEV_DB_PASS="${DEV_DB_PASS:-assistencias_dev}"
DEV_DB_NAME="${DEV_DB_NAME:-assistencias_dev}"

TEST_DB_USER="${TEST_DB_USER:-assistencias_test}"
TEST_DB_PASS="${TEST_DB_PASS:-assistencias_test}"
TEST_DB_NAME="${TEST_DB_NAME:-assistencias_test}"

die() {
  echo "ERRO: $*" >&2
  exit 1
}

sql_quote() {
  printf "%s" "$1" | sed "s/'/''/g"
}

validate_identifier() {
  local name="$1"
  local value="$2"
  if [[ ! "${value}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    die "${name} invalido para uso como identificador PostgreSQL: ${value}"
  fi
}

psql_admin() {
  sudo -u postgres psql -p "${DB_PORT}" -d "${DB_ADMIN_DB}" -v ON_ERROR_STOP=1 "$@"
}

role_exists() {
  local role="$1"
  local role_lit
  role_lit="$(sql_quote "${role}")"
  [[ "$(psql_admin -Atc "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '${role_lit}'")" == "1" ]]
}

ensure_role() {
  local role="$1"
  local pass="$2"
  local grant_createdb="${3:-false}"
  local pass_lit
  pass_lit="$(sql_quote "${pass}")"

  if role_exists "${role}"; then
    echo "Role ${role} ja existe; atualizando senha local."
  else
    echo "Criando role ${role}."
    psql_admin -c "CREATE ROLE \"${role}\" LOGIN PASSWORD '${pass_lit}';"
  fi

  psql_admin -c "ALTER ROLE \"${role}\" LOGIN PASSWORD '${pass_lit}';"

  if [[ "${grant_createdb}" == "true" ]]; then
    echo "Concedendo CREATEDB ao role local de teste ${role}."
    psql_admin -c "ALTER ROLE \"${role}\" CREATEDB;"
  fi
}

database_owner() {
  local db_name="$1"
  local db_lit
  db_lit="$(sql_quote "${db_name}")"
  psql_admin -Atc "SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_catalog.pg_database WHERE datname = '${db_lit}'"
}

ensure_database() {
  local db_name="$1"
  local owner="$2"
  local current_owner
  current_owner="$(database_owner "${db_name}")"

  if [[ -z "${current_owner}" ]]; then
    echo "Criando database ${db_name} com owner ${owner}."
    sudo -u postgres createdb -p "${DB_PORT}" -O "${owner}" "${db_name}"
  elif [[ "${current_owner}" != "${owner}" ]]; then
    echo "AVISO: database ${db_name} pertence a ${current_owner}; ajustando owner para ${owner}."
    psql_admin -c "ALTER DATABASE \"${db_name}\" OWNER TO \"${owner}\";"
  else
    echo "Database ${db_name} ja existe com owner ${owner}."
  fi
}

echo "[0/7] Validando ambiente..."

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "ERRO: Python não encontrado: ${PYTHON_BIN}"
  exit 1
fi

PY_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

if [[ "${PY_VERSION}" != "3.10" ]]; then
  echo "ERRO: este projeto está padronizado para Python 3.10 no Ubuntu 22.04 LTS."
  echo "Python detectado: ${PY_VERSION}"
  echo "Use Ubuntu 22.04.5 LTS ou rode com: PYTHON_BIN=python3.10 ./scripts/dev_wsl_bootstrap.sh"
  exit 1
fi

echo "Python OK: $("${PYTHON_BIN}" --version)"

validate_identifier "DEV_DB_USER" "${DEV_DB_USER}"
validate_identifier "DEV_DB_NAME" "${DEV_DB_NAME}"
validate_identifier "TEST_DB_USER" "${TEST_DB_USER}"
validate_identifier "TEST_DB_NAME" "${TEST_DB_NAME}"

echo "[1/7] Instalando dependências de sistema..."
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  curl \
  git \
  libffi-dev \
  libpq-dev \
  postgresql \
  postgresql-contrib \
  python3 \
  python3-dev \
  python3-pip \
  python3-venv

echo "[2/7] Inicializando PostgreSQL..."
sudo service postgresql start

echo "[3/7] Criando usuários e bancos de desenvolvimento/teste..."
ensure_role "${DEV_DB_USER}" "${DEV_DB_PASS}" false
ensure_role "${TEST_DB_USER}" "${TEST_DB_PASS}" true
ensure_database "${DEV_DB_NAME}" "${DEV_DB_USER}"
ensure_database "${TEST_DB_NAME}" "${TEST_DB_USER}"

echo "[4/7] Criando ambiente virtual em ${VENV_DIR}..."
if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

echo "Python no venv: $(python --version)"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

echo "[5/7] Preparando .env..."
if [[ ! -f .env ]]; then
  cp .env.example .env
fi

python - <<PY
from pathlib import Path

env_path = Path('.env')
text = env_path.read_text(encoding='utf-8') if env_path.exists() else ''

updates = {
    'FLASK_ENV': 'development',
    'FLASK_DEBUG': '1',
    'FLASK_APP': 'run.py',
    'DATABASE_URI': 'postgresql://${DEV_DB_USER}:${DEV_DB_PASS}@${DB_HOST}:${DB_PORT}/${DEV_DB_NAME}',
    'DEV_DATABASE_URI': 'postgresql://${DEV_DB_USER}:${DEV_DB_PASS}@${DB_HOST}:${DB_PORT}/${DEV_DB_NAME}',
    'TEST_DATABASE_URI': 'postgresql://${TEST_DB_USER}:${TEST_DB_PASS}@${DB_HOST}:${DB_PORT}/${TEST_DB_NAME}',
}

seen = set()
output = []
for line in text.splitlines():
    stripped = line.strip()
    if '=' not in line or stripped.startswith('#'):
        output.append(line)
        continue
    key, _value = line.split('=', 1)
    key = key.strip()
    if key in updates:
        output.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        output.append(line)

for key, value in updates.items():
    if key not in seen:
        output.append(f"{key}={value}")

env_path.write_text('\\n'.join(output) + '\\n', encoding='utf-8')
PY

echo "[6/7] Aplicando migrations no banco DEV..."
export FLASK_APP=run.py
export FLASK_ENV=development

python -m flask --app run.py db upgrade
python -m flask --app run.py db current

echo "[7/7] Validação básica..."
python - <<PY
from api import create_app
app = create_app('development')
print(f'App importada com sucesso: {app.name}')
PY

python -m compileall api scraper scripts config.py run.py >/dev/null

echo ""
echo "Bootstrap WSL concluído com sucesso."
echo ""
echo "Para ativar o ambiente:"
echo "  source ${VENV_DIR}/bin/activate"
echo ""
echo "Para rodar a API:"
echo "  python -m flask --app run.py run --debug --host 0.0.0.0 --port 5000"
echo ""
