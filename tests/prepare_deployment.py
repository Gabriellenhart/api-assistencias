import os
import shutil
from pathlib import Path

def prepare_deployment():
    """Prepara o diretório de distribuição para deploy na Webdock."""
    source_dir = Path('.')
    dist_dir = Path('dist_webdock')
    
    # Limpa diretório de distribuição se existir
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir()
    
    print(f"Criando pacote de deploy em: {dist_dir.absolute()}")
    
    # Arquivos e diretórios para copiar
    includes = [
        'api',
        'config.py',
        'run.py',
        'requirements.txt',
        # 'pyproject.toml', # Opcional se usar requirements.txt
        'gunicorn_config.py',
        'nginx-config',
        'assistencias-api.service',
        'backup_database.py',
        'restore_database.py',
        'setup_vps.sh' # Vamos criar este arquivo depois
    ]
    
    for item in includes:
        src = source_dir / item
        dst = dist_dir / item
        
        if not src.exists():
            print(f"Aviso: '{item}' não encontrado. Pulando.")
            continue
            
        if src.is_dir():
            # Copia diretório recursivamente, ignorando __pycache__
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            print(f"Copiado diretório: {item}")
        else:
            shutil.copy2(src, dst)
            print(f"Copiado arquivo: {item}")
            
    # Cria .env de exemplo
    env_content = """# Configurações de Produção
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=gere_uma_chave_segura_aqui
JWT_SECRET_KEY=gere_outra_chave_segura_aqui

# Banco de Dados (PostgreSQL)
# O script de setup irá configurar isso, mas mantenha o padrão:
DEV_DATABASE_URI='postgresql://usuario_db:senha_segura@localhost:5432/assistencias_prod'
DATABASE_URL='postgresql://usuario_db:senha_segura@localhost:5432/assistencias_prod'
"""
    with open(dist_dir / '.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    print("Criado arquivo: .env (template)")
    
    print("\nPacote 'dist_webdock' criado com sucesso!")
    print("Agora adicione o arquivo 'setup_vps.sh' e copie a pasta para sua VPS.")

if __name__ == "__main__":
    prepare_deployment()
