#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

die() {
  printf '[dev reset_db] ERRO: %s\n' "$*" >&2
  exit 1
}

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

if [[ "${FLASK_ENV}" == "production" ]]; then
  die "reset bloqueado: FLASK_ENV=production."
fi

DB_URI="${DEV_DATABASE_URI:-${DATABASE_URI:-}}"
[[ -n "${DB_URI}" ]] || die "DEV_DATABASE_URI ou DATABASE_URI nao definido."

case "${DB_URI}" in
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

IFS='|' read -r DB_HOST DB_PORT DB_USER DB_PASS DB_NAME <<<"${DB_INFO}"
[[ -n "${DB_NAME}" ]] || die "nome do banco nao encontrado na URI."

echo "[dev reset_db] Banco alvo: ${DB_NAME} em ${DB_HOST}:${DB_PORT}, usuario ${DB_USER}"
echo "[dev reset_db] Esta acao apaga dados locais de desenvolvimento."
read -r -p "Digite RESET para confirmar: " CONFIRM
[[ "${CONFIRM}" == "RESET" ]] || die "confirmacao invalida; abortado."

command -v dropdb >/dev/null 2>&1 || die "dropdb nao encontrado."
command -v createdb >/dev/null 2>&1 || die "createdb nao encontrado."

export PGPASSWORD="${DB_PASS}"
dropdb --if-exists -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" "${DB_NAME}"
createdb -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" "${DB_NAME}"
unset PGPASSWORD

echo "[dev reset_db] aplicando migrations"
python -m flask db upgrade

cat <<'MSG'
[dev reset_db] concluido.
Para recriar admin inicial interativamente:
  python -m flask --app run.py create-admin
MSG
