#!/usr/bin/env bash
# setup_vps.sh
# Provisiona infraestrutura Linux para a API (VPS/Webdock).
# Execute como root: sudo bash setup_vps.sh

set -euo pipefail

APP_DIR="/var/www/assistencias-api"
VENV_DIR="${APP_DIR}/venv"
DB_NAME="assistencias_prod"
DB_USER="monitoramento"
DB_PASS_DEFAULT="monitoramento@100"
BACKUP_HOUR="3"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        echo -e "${RED}Erro: execute como root (sudo).${NC}"
        exit 1
    fi
}

require_file() {
    local file="$1"
    if [[ ! -f "${file}" ]]; then
        echo -e "${RED}Arquivo obrigatorio nao encontrado: ${file}${NC}"
        exit 1
    fi
}

start_postgres() {
    if command -v systemctl >/dev/null 2>&1; then
        systemctl enable --now postgresql
    else
        service postgresql start
    fi
}

require_root

echo -e "${GREEN}=== Iniciando Setup da API na VPS ===${NC}"
echo "Diretorio alvo: ${APP_DIR}"

require_file "requirements.txt"
require_file "assistencias-api.service"
require_file "nginx-config"
require_file "run.py"

echo -e "${YELLOW}[1/8] Atualizando pacotes do sistema...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt update
apt upgrade -y

echo -e "${YELLOW}[2/8] Instalando dependencias...${NC}"
apt install -y \
    python3-pip python3-venv python3-dev libpq-dev \
    postgresql postgresql-contrib nginx curl git acl \
    rsync ca-certificates

echo -e "${YELLOW}[3/8] Preparando diretorio da aplicacao...${NC}"
mkdir -p "${APP_DIR}/backups"

SOURCE_DIR="$(pwd -P)"
TARGET_DIR="$(realpath "${APP_DIR}")"
if [[ "${SOURCE_DIR}" != "${TARGET_DIR}" ]]; then
    rsync -a \
        --exclude '.git/' \
        --exclude '.venv/' \
        --exclude 'venv/' \
        --exclude '__pycache__/' \
        --exclude '*.pyc' \
        --exclude 'backups/' \
        --exclude 'logs/' \
        --exclude 'uploads/' \
        --exclude 'dist_webdock/' \
        --exclude '.env' \
        "${SOURCE_DIR}/" "${APP_DIR}/"
else
    echo "Script executado dentro do diretorio de destino; copia ignorada."
fi

chown -R www-data:www-data "${APP_DIR}"
chmod -R 755 "${APP_DIR}"

echo -e "${YELLOW}[4/8] Configurando Python e instalando dependencias...${NC}"
cd "${APP_DIR}"

if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
fi

if file requirements.txt | grep -q "UTF-16"; then
    echo "requirements.txt em UTF-16 detectado; convertendo para UTF-8."
    iconv -f UTF-16 -t UTF-8 requirements.txt -o requirements.txt.tmp
    mv requirements.txt.tmp requirements.txt
fi
sed -i '1s/^\xEF\xBB\xBF//' requirements.txt

"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r requirements.txt

echo -e "${YELLOW}[5/8] Configurando PostgreSQL...${NC}"
start_postgres

echo ""
echo -e "${RED}Defina a senha do banco para o usuario '${DB_USER}'.${NC}"
read -r -s -p "Senha (Enter para padrao inseguro): " DB_PASS
echo ""
if [[ -z "${DB_PASS}" ]]; then
    DB_PASS="${DB_PASS_DEFAULT}"
    echo -e "${RED}Aviso: senha padrao em uso. Troque apos instalar.${NC}"
fi

sudo -u postgres psql -v ON_ERROR_STOP=1 \
    --set=db_user="${DB_USER}" \
    --set=db_pass="${DB_PASS}" \
    --set=db_name="${DB_NAME}" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_pass')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user') \gexec

SELECT format('ALTER ROLE %I WITH PASSWORD %L', :'db_user', :'db_pass') \gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \gexec

SELECT format('GRANT ALL PRIVILEGES ON DATABASE %I TO %I', :'db_name', :'db_user') \gexec
SQL

echo "Banco de dados configurado."

DB_PASS_ENCODED="$("${VENV_DIR}/bin/python" -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "${DB_PASS}")"
DB_URI="postgresql://${DB_USER}:${DB_PASS_ENCODED}@localhost/${DB_NAME}"

if [[ -f ".env" ]]; then
    cp .env ".env.bak.$(date +%Y%m%d%H%M%S)"
else
    touch .env
fi

grep -vE '^(DATABASE_URI|DEV_DATABASE_URI|TEST_DATABASE_URI|FLASK_DEBUG|FLASK_ENV)=' .env > .env.tmp || true
mv .env.tmp .env
echo "FLASK_ENV=production" >> .env
echo "FLASK_DEBUG=0" >> .env
echo "DATABASE_URI='${DB_URI}'" >> .env

if ! grep -q '^SECRET_KEY=' .env; then
    echo "SECRET_KEY='$(openssl rand -hex 32)'" >> .env
fi

chown www-data:www-data .env
chmod 640 .env

echo ".env atualizado para producao."

echo -e "${YELLOW}[6/8] Configurando Systemd e Nginx...${NC}"
mkdir -p /var/log/gunicorn
chown -R www-data:www-data /var/log/gunicorn

cp assistencias-api.service /etc/systemd/system/assistencias-api.service
systemctl daemon-reload
systemctl enable assistencias-api

cp nginx-config /etc/nginx/sites-available/assistencias-api
ln -sf /etc/nginx/sites-available/assistencias-api /etc/nginx/sites-enabled/assistencias-api
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

echo -e "${YELLOW}[7/8] Verificando restauracao de backup...${NC}"
shopt -s nullglob
incoming_dumps=("${APP_DIR}"/*backup*.dump)
if (( ${#incoming_dumps[@]} > 0 )); then
    mv "${incoming_dumps[@]}" "${APP_DIR}/backups/"
fi

dump_files=("${APP_DIR}/backups/"*.dump)
if (( ${#dump_files[@]} > 0 )); then
    echo "Backups encontrados: ${#dump_files[@]}"
    read -r -p "Restaurar backup agora? (s/n): " RESTORE_OPT
    if [[ "${RESTORE_OPT}" == "s" || "${RESTORE_OPT}" == "S" ]]; then
        export DATABASE_URI="${DB_URI}"
        "${VENV_DIR}/bin/python" restore_database.py
    else
        export FLASK_APP=run.py
        "${VENV_DIR}/bin/flask" db upgrade
    fi
else
    echo "Nenhum backup encontrado; aplicando migrations."
    export FLASK_APP=run.py
    "${VENV_DIR}/bin/flask" db upgrade
fi
shopt -u nullglob

systemctl restart assistencias-api

echo -e "${YELLOW}[8/8] Configurando backup diario (cron)...${NC}"
BACKUP_CMD="${VENV_DIR}/bin/python ${APP_DIR}/backup_database.py >> ${APP_DIR}/backups/backup.log 2>&1"
(crontab -l 2>/dev/null | grep -v "backup_database.py"; echo "0 ${BACKUP_HOUR} * * * ${BACKUP_CMD}") | crontab -

chown -R www-data:www-data "${APP_DIR}"

PUBLIC_IP="$(curl -s --max-time 5 ifconfig.me || true)"
echo -e "${GREEN}=== Setup concluido com sucesso ===${NC}"
if [[ -n "${PUBLIC_IP}" ]]; then
    echo "API disponivel em: http://${PUBLIC_IP}"
fi
echo "Status do servico: systemctl status assistencias-api"
