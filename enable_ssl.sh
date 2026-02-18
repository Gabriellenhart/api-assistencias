#!/bin/bash
# enable_ssl.sh
# Habilita HTTPS usando Certbot (Let's Encrypt)
# Execute como ROOT (sudo)

set -e

DOMAIN="monitoramen1.vps.webdock.cloud"
EMAIL="augustolenhart@gmail.com"

echo "=== Habilitando SSL para $DOMAIN ==="

# 1. Instalar Certbot e plugin Nginx
echo "Instalando Certbot..."
apt update
apt install -y certbot python3-certbot-nginx

# 2. Obter Certificado e Configurar Nginx
echo "Obtendo certificado..."
# --nginx: Usa o plugin nginx para configurar automaticamente
# --non-interactive: Não faz perguntas
# --agree-tos: Aceita termos de serviço
# --redirect: Força redirecionamento HTTP -> HTTPS
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL --redirect

echo "=== SUCESSO! ==="
echo "HTTPS habilitado. Acesse: https://$DOMAIN"
echo "OBS: O Certbot configurou a renovação automática."
