import os

print("--- FIX PRODUCTION ENV ---")
env_file = '.env'

if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Verifica se FLASK_ENV já existe
    if 'FLASK_ENV=production' not in content:
        print("Adicionando FLASK_ENV=production ao .env...")
        with open(env_file, 'a') as f:
            f.write('\nFLASK_ENV=production\n')
        print("[OK] Arquivo atualizado.")
    else:
        print("[INFO] FLASK_ENV=production já existe.")
        
    print("Reiniciando serviço...")
    os.system("sudo systemctl restart assistencias-api")
    print("[SUCESSO] API reiniciada em modo PRODUÇÃO.")
else:
    print("[ERRO] Arquivo .env não encontrado.")
