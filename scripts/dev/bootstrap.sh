#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

log() {
  printf '[dev bootstrap] %s\n' "$*"
}

die() {
  printf '[dev bootstrap] ERRO: %s\n' "$*" >&2
  exit 1
}

case "$(uname -s 2>/dev/null || echo unknown)" in
  Linux*) ;;
  *)
    die "este script foi pensado para Linux/WSL. No Windows, use scripts/dev/bootstrap.ps1 ou rode via WSL."
    ;;
esac

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

command -v "${PYTHON_BIN}" >/dev/null 2>&1 || die "python3 nao encontrado."
"${PYTHON_BIN}" --version

if [[ ! -d "${VENV_DIR}" ]]; then
  log "criando virtualenv em ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

log "atualizando pip e instalando requirements.txt"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [[ ! -f .env ]]; then
  log "criando .env a partir de .env.example"
  cp .env.example .env
  log "revise .env antes de usar credenciais reais. Nunca versionar .env."
else
  log ".env ja existe; nao sera sobrescrito"
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

export FLASK_APP="${FLASK_APP:-run.py}"
export FLASK_ENV="${FLASK_ENV:-development}"
export FLASK_DEBUG="${FLASK_DEBUG:-1}"

DB_URI="${DEV_DATABASE_URI:-${DATABASE_URI:-}}"
if [[ -z "${DB_URI}" ]]; then
  die "DEV_DATABASE_URI ou DATABASE_URI precisa estar definido no .env."
fi

log "verificando PostgreSQL"
if ! command -v psql >/dev/null 2>&1; then
  cat <<'MSG'
[dev bootstrap] psql nao encontrado.
Instale o cliente PostgreSQL e crie o banco local manualmente.
Exemplo:
  sudo apt-get install postgresql postgresql-client
  sudo -u postgres createuser --login assistencias_dev
  sudo -u postgres psql -c "ALTER USER assistencias_dev WITH PASSWORD 'assistencias_dev';"
  sudo -u postgres createdb -O assistencias_dev assistencias_dev
MSG
  die "PostgreSQL client indisponivel."
fi

if ! python - <<'PY'
import os
import sys
from urllib.parse import urlparse

uri = os.environ.get("DEV_DATABASE_URI") or os.environ.get("DATABASE_URI")
parsed = urlparse(uri)
if parsed.scheme not in {"postgresql", "postgresql+psycopg2"}:
    print("URI de banco nao parece PostgreSQL.", file=sys.stderr)
    sys.exit(2)

print(parsed.hostname or "localhost")
PY
then
  die "URI de banco invalida."
fi

log "testando conexao com o banco local"
if ! python - <<'PY'
import os
import sys
import psycopg2

uri = os.environ.get("DEV_DATABASE_URI") or os.environ.get("DATABASE_URI")
try:
    conn = psycopg2.connect(uri)
    conn.close()
except Exception as exc:
    print(f"Nao foi possivel conectar ao banco: {exc}", file=sys.stderr)
    sys.exit(1)
PY
then
  cat <<'MSG'
[dev bootstrap] ajuste DEV_DATABASE_URI em .env e garanta que o banco existe.
Exemplo recomendado:
  DEV_DATABASE_URI=postgresql://assistencias_dev:assistencias_dev@localhost:5432/assistencias_dev
MSG
  exit 1
fi

log "aplicando migrations"
python -m flask db upgrade

log "executando validacao rapida"
bash scripts/dev/check.sh

cat <<'MSG'
[dev bootstrap] concluido.
Para criar admin inicial interativamente, rode:
  source .venv/bin/activate
  python -m flask --app run.py create-admin

Para iniciar a API:
  ./scripts/dev/run.sh
MSG
