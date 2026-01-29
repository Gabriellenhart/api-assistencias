#!/bin/bash
# setup_vps.sh
# Script de automação de infraestrutura para Webdock VPS
# AVISO: Execute como ROOT ou sudo

set -e

# --- Configurações ---
APP_DIR="/var/www/assistencias-api"
VENV_DIR="$APP_DIR/venv"
REPO_FILES="." # Assume que estamos rodando dentro da pasta com os arquivos enviados
DB_NAME="assistencias_prod"
DB_USER="monitoramento"
# Senha padrão, o script pedirá para mudar
DB_PASS_DEFAULT="monitoramento@100" 

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Iniciando Setup Automático da API (Webdock) ===${NC}"

# 1. Atualização do Sistema
echo -e "${YELLOW}[1/8] Atualizando pacotes do sistema...${NC}"
apt update && apt upgrade -y

# 2. Instalação de Dependências
echo -e "${YELLOW}[2/8] Instalando dependências (Python, Postgres, Nginx)...${NC}"
apt install -y python3-pip python3-venv python3-dev libpq-dev postgresql postgresql-contrib nginx curl git acl

# 3. Preparação do Diretório da Aplicação
echo -e "${YELLOW}[3/8] Configurando diretório da aplicação em $APP_DIR...${NC}"
mkdir -p $APP_DIR
# Copia arquivos do diretório atual para o diretório de instalação
if [ "$(realpath .)" != "$(realpath $APP_DIR)" ]; then
    cp -r ./* $APP_DIR/
else
    echo "Rodando dentro do diretório de destino, pulando cópia."
fi
# Cria diretório de backups
mkdir -p $APP_DIR/backups
# Ajusta permissões iniciais
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR
# Adiciona seu usuário ao grupo www-data para facilitar edições (opcional, assume root por enquanto)
# usermod -aG www-data ubuntu

# 4. Configuração do Python (Venv)
echo -e "${YELLOW}[4/8] Criando ambiente virtual e instalando dependências Python...${NC}"
cd $APP_DIR
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Venv criado."
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
echo "Dependências Python instaladas."

# 5. Configuração do Banco de Dados
echo -e "${YELLOW}[5/8] Configurando PostgreSQL...${NC}"
# Verifica se o banco já existe
start_postgres() {
    service postgresql start
}
start_postgres

# Solicita senha segura
echo ""
echo -e "${RED}IMPORTANTE: Defina uma senha segura para o banco de dados produção.${NC}"
read -s -p "Digite a senha para o usuário '$DB_USER': " DB_PASS
echo ""
if [ -z "$DB_PASS" ]; then
    DB_PASS=$DB_PASS_DEFAULT
    echo "Usando senha padrão (NÃO RECOMENDADO)."
fi

# Cria usuário e banco se não existirem
sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename = '$DB_USER'" | grep -q 1 || sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

echo "Banco de dados configurado."

# Atualiza .env com a senha correta
echo -e "${YELLOW}Atualizando .env com credenciais...${NC}"

# Encode password to avoid URI issues
DB_PASS_ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$DB_PASS'''))")

if [ -f ".env" ]; then
    # Força ambiente de produção
    sed -i 's/FLASK_ENV=.*/FLASK_ENV=production/' .env
    
    # Remove configurações antigas de banco para evitar conflito
    sed -i '/DATABASE_URI=/d' .env
    
    # Adiciona a URI correta de produção
    echo "" >> .env
    echo "DATABASE_URI='postgresql://$DB_USER:$DB_PASS_ENCODED@localhost/$DB_NAME'" >> .env
    
    echo "Arquivo .env atualizado para Produção."
else
    echo "Criando novo arquivo .env..."
    echo "FLASK_ENV=production" > .env
    echo "SECRET_KEY='$(openssl rand -hex 32)'" >> .env
    echo "DATABASE_URI='postgresql://$DB_USER:$DB_PASS_ENCODED@localhost/$DB_NAME'" >> .env
fi

# 6. Configuração do Servidor (Nginx e Systemd)
echo -e "${YELLOW}[6/8] Configurando Nginx e Systemd...${NC}"

# Cria diretório de logs do Gunicorn
mkdir -p /var/log/gunicorn
# Ajusta permissões para o usuário do serviço (definido no assistencias-api.service como www-data)
chown -R www-data:www-data /var/log/gunicorn

# --- SSL SETUP (Executar Manualmente) ---
# Para habilitar HTTPS, rode:
# apt install -y certbot python3-certbot-nginx
# certbot --nginx -d monitoramen1.vps.webdock.cloud --non-interactive --agree-tos -m augustolenhart@gmail.com
# ----------------------------------------

# Systemd
cp assistencias-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable assistencias-api
systemctl restart assistencias-api

# Nginx
cp nginx-config /etc/nginx/sites-available/assistencias-api
ln -sf /etc/nginx/sites-available/assistencias-api /etc/nginx/sites-enabled/
# Remove default se existir
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# 7. Restauração de Backup (Opcional)
echo -e "${YELLOW}[7/8] Verificando backups para restauração...${NC}"
# Procura arquivos .dump na raiz e move para backups/
mv *backup*.dump backups/ 2>/dev/null || true

DUMP_COUNT=$(ls backups/*.dump 2>/dev/null | wc -l)

if [ "$DUMP_COUNT" != "0" ]; then
    echo "Encontrados $DUMP_COUNT arquivos de backup."
    read -p "Deseja restaurar um backup agora? (s/n): " RESTORE_OPT
    if [ "$RESTORE_OPT" == "s" ]; then
        echo "Executando script de restauração Python..."
        # Passa a URI explicitamente usando as variaveis do script para evitar erros de .env antigo
        export DATABASE_URI="postgresql://$DB_USER:$DB_PASS_ENCODED@localhost/$DB_NAME"
        python3 restore_database.py
    fi
else
    echo "Nenhum arquivo .dump encontrado para restaurar."
    echo "Inicializando banco vazio com migrações..."
    export FLASK_APP=run.py
    flask db upgrade
fi

# 8. Automação de Backup (Cron)
echo -e "${YELLOW}[8/8] Configurando backup diário (Cron)...${NC}"
BACKUP_CMD="$APP_DIR/venv/bin/python $APP_DIR/backup_database.py >> $APP_DIR/backups/backup.log 2>&1"
# Adiciona job no cron se não existir (roda as 03:00 am)
(crontab -l 2>/dev/null | grep -v "backup_database.py"; echo "0 3 * * * $BACKUP_CMD") | crontab -
echo "Cron job adicionado: Executa backup todo dia às 03:00."

# Permissões finais
chown -R www-data:www-data $APP_DIR

echo -e "${GREEN}=== Setup Concluído! ===${NC}"
echo "Sua API deve estar rodando em http://$(curl -s ifconfig.me) ou no domínio configurado."
echo "Para verificar status: systemctl status assistencias-api"
