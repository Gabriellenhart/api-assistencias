import os
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

# Tenta importar python-dotenv, mas não falha se não existir (assume variáveis de ambiente já carregadas ou não necessárias se hardcoded - o que não é o caso aqui, mas boa prática)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Aviso: python-dotenv não instalado. Certifique-se de que as variáveis de ambiente estão configuradas.")

def get_database_config():
    """Recupera as configurações do banco de dados das variáveis de ambiente."""
    # Tenta pegar URI de diferentes variáveis comuns
    db_uri = os.getenv('DEV_DATABASE_URI') or os.getenv('DATABASE_URL')
    
    if not db_uri:
        print("Erro: Nenhuma URI de banco de dados encontrada em .env (DEV_DATABASE_URI ou DATABASE_URL).")
        sys.exit(1)
        
    return db_uri

def parse_db_uri(uri):
    """Analisa a URI do banco de dados e retorna os componentes."""
    result = urlparse(uri)
    return {
        'dbname': result.path[1:],
        'user': result.username,
        'password': result.password,
        'host': result.hostname,
        'port': result.port or 5432
    }

def create_backup():
    """Executa o backup do banco de dados."""
    db_uri = get_database_config()
    config = parse_db_uri(db_uri)
    
    # Diretório de backup
    backup_dir = Path('backups')
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = backup_dir / f"backup_assistencias_{timestamp}.dump"
    
    print(f"Iniciando backup de '{config['dbname']}' em '{config['host']}'...")
    print(f"Arquivo de destino: {filename}")
    
    # Prepara o ambiente para o pg_dump (senha)
    env = os.environ.copy()
    if config['password']:
        env['PGPASSWORD'] = config['password']
    
    # Comando pg_dump
    # -F c: Formato Custom (necessário para pg_restore)
    # -v: Verbose
    # -f: Arquivo de saída
    command = [
        'pg_dump',
        '-h', config['host'],
        '-p', str(config['port']),
        '-U', config['user'],
        '-F', 'c',
        '-v',
        '-f', str(filename),
        config['dbname']
    ]
    
    try:
        subprocess.run(command, env=env, check=True)
        print("\nBackup concluído com sucesso!")
        return str(filename)
    except subprocess.CalledProcessError as e:
        print(f"\nErro ao executar pg_dump: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\nErro: 'pg_dump' não encontrado. Certifique-se de que o PostgreSQL está instalado e o pg_dump está no PATH do sistema.")
        sys.exit(1)

if __name__ == "__main__":
    create_backup()
