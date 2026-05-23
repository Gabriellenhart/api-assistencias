#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

die() {
  printf '[dev reset_db] ERRO: %s\n' "$*" >&2
  exit 1
}

YES=0
case "${1:-}" in
  --yes)
    YES=1
    ;;
  "")
    ;;
  *)
    die "uso: $0 [--yes]"
    ;;
esac

[[ -d .venv ]] || die ".venv nao encontrado. Rode ./scripts/dev/bootstrap.sh primeiro."
# shellcheck disable=SC1091
source .venv/bin/activate

[[ -f .env ]] || die ".env nao encontrado."
set -a
# shellcheck disable=SC1091
source .env
set +a

export FLASK_APP="${FLASK_APP:-run.py}"
export FLASK_ENV="${FLASK_ENV:-development}"

if [[ "${FLASK_ENV,,}" == "production" ]]; then
  die "reset bloqueado: FLASK_ENV=production."
fi

DB_URI="${DEV_DATABASE_URI:-${DATABASE_URI:-}}"
[[ -n "${DB_URI}" ]] || die "DEV_DATABASE_URI ou DATABASE_URI nao definido."

case "${DB_URI,,}" in
  *prod*|*production*|*rds.amazonaws.com*|*render.com*|*railway.app*|*neon.tech*)
    die "reset bloqueado: URI parece apontar para producao."
    ;;
esac

DB_INFO="$(python - <<'PY'
import os
from urllib.parse import urlparse

uri = os.environ.get("DEV_DATABASE_URI") or os.environ.get("DATABASE_URI")
p = urlparse(uri)
print("|".join([
    p.hostname or "localhost",
    str(p.port or 5432),
    p.username or "",
    p.password or "",
    (p.path or "/").lstrip("/"),
]))
PY
)"

IFS='|' read -r DB_HOST DB_PORT DB_USER _DB_PASS DB_NAME <<<"${DB_INFO}"
[[ -n "${DB_NAME}" ]] || die "nome do banco nao encontrado na URI."

EXPECTED_DB_USER="${DEV_DB_USER:-assistencias_dev}"
EXPECTED_DB_NAME="${DEV_DB_NAME:-assistencias_dev}"

case "${DB_HOST}" in
  localhost|127.0.0.1|::1) ;;
  *) die "reset bloqueado: host '${DB_HOST}' nao e local." ;;
esac

[[ "${DB_NAME}" == "${EXPECTED_DB_NAME}" ]] || die "reset bloqueado: banco '${DB_NAME}' difere de '${EXPECTED_DB_NAME}'."
[[ "${DB_USER}" == "${EXPECTED_DB_USER}" ]] || die "reset bloqueado: usuario '${DB_USER}' difere de '${EXPECTED_DB_USER}'."

echo "[dev reset_db] Banco alvo: ${DB_NAME} em ${DB_HOST}:${DB_PORT}, usuario ${DB_USER}"
echo "[dev reset_db] Esta acao apaga dados locais de desenvolvimento."
if [[ "${YES}" != "1" ]]; then
  read -r -p "Digite RESET para confirmar: " CONFIRM
  [[ "${CONFIRM}" == "RESET" ]] || die "confirmacao invalida; abortado."
fi

command -v sudo >/dev/null 2>&1 || die "sudo nao encontrado."
command -v psql >/dev/null 2>&1 || die "psql nao encontrado."

echo "[dev reset_db] encerrando conexoes e recriando banco via usuario postgres local"
sudo -u postgres psql -p "${DB_PORT}" -d postgres -v ON_ERROR_STOP=1 \
  -v db_name="${DB_NAME}" \
  -v db_owner="${EXPECTED_DB_USER}" <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = :'db_name'
  AND pid <> pg_backend_pid();

DROP DATABASE IF EXISTS :"db_name";
CREATE DATABASE :"db_name" OWNER :"db_owner";
SQL

echo "[dev reset_db] aplicando migrations"
python -m flask --app run.py db upgrade
python -m flask --app run.py db current

cat <<'MSG'
[dev reset_db] concluido.
Para recriar admin inicial interativamente:
  python -m flask --app run.py create-admin
MSG
