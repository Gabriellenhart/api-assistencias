import os
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Aviso: python-dotenv não instalado. Continuando...")

def get_database_config():
    """Recupera as configurações do banco de dados das variáveis de ambiente."""
    # Tenta pegar URI de diferentes variáveis
    db_uri = os.getenv('DEV_DATABASE_URI') or os.getenv('DATABASE_URL') or os.getenv('DATABASE_URI')
    
    if not db_uri:
        # Se não achar nada, tenta um padrão local comum para evitar falha
        print("Aviso: Nenhuma URI encontrada. Tentando padrão local postgresql://postgres:postgres@localhost/assistencias_db")
        return "postgresql://postgres:postgres@localhost/assistencias_db"
        
    return db_uri

def parse_db_uri(uri):
    result = urlparse(uri)
    return {
        'dbname': result.path[1:],
        'user': result.username,
        'password': result.password,
        'host': result.hostname,
        'port': result.port or 5432
    }

def create_plain_backup():
    """Executa o backup do banco de dados em formato Plain (SQL)."""
    db_uri = get_database_config()
    config = parse_db_uri(db_uri)
    
    backup_dir = Path('backups')
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # Extensão .sql para identificar formato texto
    filename = backup_dir / f"backup_assistencias_plain_{timestamp}.sql"
    
    print(f"Iniciando backup PLAIN (SQL) de '{config['dbname']}' em '{config['host']}'...")
    print(f"Arquivo de destino: {filename}")
    
    env = os.environ.copy()
    if config['password']:
        env['PGPASSWORD'] = config['password']
    
    # Comando pg_dump
    # -F p: Formato Plain (Texto SQL) - CRUCIAL PARA COMPATIBILIDADE DE VERSAO
    # -v: Verbose
    # -f: Arquivo de saída
    # --clean: Inclui comandos DROP antes de CREATE
    # --if-exists: Usa DROP IF EXISTS
    command = [
        'pg_dump',
        '-h', config['host'],
        '-p', str(config['port']),
        '-U', config['user'],
        '-F', 'p',     # Plain Text
        '--clean',     # Adiciona DROP commands
        '--if-exists',
        '-v',
        '-f', str(filename),
        config['dbname']
    ]
    
    try:
        subprocess.run(command, env=env, check=True)
        print("\nBackup Plain SQL concluído com sucesso!")
        print(f"ENVIA ESTE ARQUIVO PARA VPS: {filename}")
        return str(filename)
    except subprocess.CalledProcessError as e:
        print(f"\nErro ao executar pg_dump: {e}")
        print("Verifique se o caminho do PostgreSQL/bin está nas variáveis de ambiente.")
        sys.exit(1)
    except FileNotFoundError:
        print("\nErro: 'pg_dump' não encontrado. Certifique-se de que o PostgreSQL está instalado e o pg_dump está no PATH do sistema.")
        sys.exit(1)

if __name__ == "__main__":
    create_plain_backup()
