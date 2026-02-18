import os
import subprocess
import sys
import platform
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

# Tenta importar python-dotenv
def load_env_manual():
    """Carrega .env manualmente se python-dotenv não estiver disponível."""
    env_path = Path('.env')
    if not env_path.exists():
        return
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip("'\"")
                os.environ[key] = value

# Tenta importar python-dotenv, se falhar usa o manual
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    load_env_manual()

def get_database_config():
    """Recupera as configurações do banco de dados das variáveis de ambiente."""
    db_uri = os.getenv('DATABASE_URI') or os.getenv('DEV_DATABASE_URI') or os.getenv('DATABASE_URL')
    
    if not db_uri:
        print("Erro: Nenhuma URI de banco de dados encontrada em .env (DATABASE_URI, DEV_DATABASE_URI ou DATABASE_URL).")
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

def list_backups(backup_dir):
    """Lista arquivos de backup disponíveis, ordenados por data."""
    if not backup_dir.exists():
        print(f"Diretório de backups '{backup_dir}' não encontrado.")
        return []
    
    files = sorted(list(backup_dir.glob('*.dump')) + list(backup_dir.glob('*.sql')), key=os.path.getmtime, reverse=True)
    return files

def stop_service():
    """Para o serviço da API para liberar conexões com o banco."""
    print("Parando serviço assistencias-api...")
    try:
        subprocess.run(['systemctl', 'stop', 'assistencias-api'], check=False)
        return True
    except Exception as e:
        print(f"Aviso: Não foi possível parar o serviço: {e}")
        return False

def start_service():
    """Inicia o serviço da API."""
    print("Iniciando serviço assistencias-api...")
    try:
        subprocess.run(['systemctl', 'start', 'assistencias-api'], check=False)
        return True
    except Exception as e:
        print(f"Aviso: Não foi possível iniciar o serviço: {e}")
        return False

def restore_database():
    """Executa a restauração do banco de dados."""
    db_uri = get_database_config()
    config = parse_db_uri(db_uri)
    
    backup_dir = Path('backups')
    backups = list_backups(backup_dir)
    
    if not backups:
        print("Nenhum arquivo de backup encontrado em 'backups/'.")
        sys.exit(1)
        
    print(f"\nBackups disponíveis:")
    for i, backup in enumerate(backups):
        size_mb = backup.stat().st_size / (1024 * 1024)
        date_str = datetime.fromtimestamp(backup.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{i + 1}. {backup.name} ({size_mb:.2f} MB) - {date_str}")
        
    choice = input("\nEscolha o número do backup para restaurar (ou 'q' para sair): ")
    if choice.lower() == 'q':
        sys.exit(0)
        
    try:
        index = int(choice) - 1
        if not (0 <= index < len(backups)):
            raise ValueError()
        selected_backup = backups[index]
    except ValueError:
        print("Opção inválida.")
        sys.exit(1)
        
    print(f"\nATENÇÃO: Você está prestes a restaurar '{selected_backup.name}' no banco '{config['dbname']}'.")
    print("ISSO IRÁ SOBRESCREVER TODOS OS DADOS ATUAIS NO BANCO DE DADOS!")
    confirm = input("Digite 'RESTORE' para confirmar: ")
    
    if confirm != 'RESTORE':
        print("Operação cancelada.")
        sys.exit(0)
        
    # Prepara ambiente
    env = os.environ.copy()
    if config['password']:
        env['PGPASSWORD'] = config['password']
        
    # Tenta parar o serviço em vez de matar conexões via SQL
    stop_service()
    
    print("\nIniciando restauração...")
    
    # pg_restore -c (clean: drop DB objects properly) -v (verbose) -d target
    # Determinar comando baseado na extensão
    if selected_backup.suffix == '.sql':
        print("Backup format: SQL (Plain text). Using psql...")
        # psql -h ... -d dbname -f file.sql
        # Nota: arquivos .sql não suportam flag -c diretamente da mesma forma que pg_restore custom,
        # geralmente o arquivo .sql já deve conter DROP/CREATE se for dump completo.
        # Caso contrário, seria bom dropar o schema public antes, mas vamos assumir um dump limpo ou confiar no drop do .sql.
        
        command = [
            'psql',
            '-h', config['host'],
            '-p', str(config['port']),
            '-U', config['user'],
            '-d', config['dbname'],
            '-f', str(selected_backup)
        ]
    else:
        print("Backup format: Custom/Binary. Using pg_restore...")
        command = [
            'pg_restore',
            '-h', config['host'],
            '-p', str(config['port']),
            '-U', config['user'],
            '-d', config['dbname'],
            '-c',
            '-v',
            str(selected_backup)
        ]
    
    try:
        # pg_restore retorna exit code 0 em sucesso, mas as vezes warnings geram outros códigos.
        # check=False para podermos tratar erros manualmente se necessário, mas pg_restore costuma ser chato.
        # Vamos deixar check=True e pegar exceção.
        subprocess.run(command, env=env, check=True) # Se der erro gritante ele levanta exceção
        print("\nRestauração concluída com sucesso!")
        
    except subprocess.CalledProcessError as e:
        print(f"\nErro (ou warnings) durante o pg_restore. Código de saída: {e.returncode}")
        print("Verifique a saída acima para detalhes. O restore pode ter sido parcial ou concluído com avisos.")
        # pg_restore pode retornar 1 se houver warnings inofensivos, então não é fatal necessariamente.

    # Reinicia o serviço
    start_service()

if __name__ == "__main__":
    restore_database()
