import subprocess
import urllib.parse
import os
import sys

print("--- FIX DATABASE PASSWORD ---")
print("Este script vai sincronizar a senha do usuário 'monitoramento' no banco de dados e no arquivo .env")

# Solicitar nova senha
if len(sys.argv) > 1:
    new_password = sys.argv[1]
else:
    new_password = input("Digite a nova senha desejada para o DB: ").strip()

if not new_password:
    print("Senha invalida.")
    exit(1)

# 1. Alterar no Postgres (Requer sudo)
try:
    print(f"Alterando senha no PostgreSQL para o usuario 'monitoramento'...")
    # Escapar aspas simples na senha para o SQL, se necessario
    sql_pass = new_password.replace("'", "''")
    cmd = f"sudo -u postgres psql -c \"ALTER USER monitoramento WITH PASSWORD '{sql_pass}';\""
    subprocess.check_call(cmd, shell=True)
    print("[OK] Senha do DB atualizada.")
except subprocess.CalledProcessError:
    print("[ERRO] Falha ao executar comando psql. Verifique se vocÊ tem permissão sudo.")
    exit(1)

# 2. Atualizar .env
env_file = '.env'
if os.path.exists(env_file):
    print("Atualizando arquivo .env...")
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Codificar senha para URL
    encoded_pass = urllib.parse.quote(new_password)
    
    db_user = "monitoramento"
    db_name = "assistencias_prod"
    # Monta a nova string de conexão
    # Nota: localhost às vezes falha se o pg_hba.conf exigir senha e o script tentar unix socket sem senha. 
    # O psql acima roda como sudo postgres, então conecta.
    # A app roda via TCP/IP em localhost.
    new_uri = f"DATABASE_URI='postgresql://{db_user}:{encoded_pass}@localhost/{db_name}'\n"
    
    new_lines = []
    uri_found = False
    
    for line in lines:
        if line.strip().startswith("DATABASE_URI="):
            new_lines.append(new_uri)
            uri_found = True
        else:
            new_lines.append(line)
            
    if not uri_found:
        new_lines.append(new_uri)
        
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"[OK] Arquivo .env atualizado.")
    
    # 3. Reiniciar serviço para pegar nova env
    try:
        print("Reiniciando serviço da API...")
        subprocess.check_call("sudo systemctl restart assistencias-api", shell=True)
        print("[OK] Serviço reiniciado.")
    except:
        print("[AVISO] Não foi possível reiniciar o serviço automaticamente. Rode: sudo systemctl restart assistencias-api")

else:
    print("[ERRO] Arquivo .env não encontrado!")
    
print("\n--- SUCESSO ---")
print("Agora tente rodar o debug_vps.py novamente.")
