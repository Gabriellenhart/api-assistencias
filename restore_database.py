import os
import subprocess
import sys
import platform
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

# Tenta importar python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Aviso: python-dotenv não instalado. Certifique-se de que as variáveis de ambiente estão configuradas.")

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
    
    files = sorted(backup_dir.glob('*.dump'), key=os.path.getmtime, reverse=True)
    return files

def terminate_connections(config, env):
    """Encerra conexões ativas com o banco de dados alvo."""
    print(f"Encerrando conexões ativas com '{config['dbname']}'...")
    
    # SQL para desconectar usuários (exceto o nosso processo, se estivéssemos conectados via SQL, mas aqui é via subprocess)
    kill_sql = f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{config['dbname']}' AND pid <> pg_backend_pid();"
    
    # Conecta no banco 'postgres' (template padrão) para poder derrubar conexões do banco alvo
    command = [
        'psql',
        '-h', config['host'],
        '-p', str(config['port']),
        '-U', config['user'],
        '-d', 'postgres',
        '-c', kill_sql
    ]
    
    try:
        # Popen para capturar output se necessário, mas run é suficiente
        subprocess.run(command, env=env, check=False) # check=False pois pode falhar se não tiver permissão no postgres, mas tentamos
        return True
    except Exception as e:
        print(f"Aviso: Não foi possível encerrar conexões automaticamente: {e}")
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
        
    # Tenta encerrar conexões
    terminate_connections(config, env)
    
    print("\nIniciando restauração...")
    
    # pg_restore -c (clean: drop DB objects properly) -v (verbose) -d target
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

if __name__ == "__main__":
    restore_database()
