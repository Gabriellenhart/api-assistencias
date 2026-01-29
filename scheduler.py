import schedule
import time
import subprocess
import logging
import sys
import os

# Configuração de Log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Scheduler] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scheduler.log")
    ]
)

def run_script(script_path, description):
    logging.info(f"Iniciando tarefa: {description}")
    try:
        # Usa o mesmo interpretador Python que está rodando o scheduler
        cmd = [sys.executable, script_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            logging.info(f"Tarefa '{description}' concluída com sucesso.")
            # logging.info(f"Saída: {result.stdout[:200]}...") 
        else:
            logging.error(f"Tarefa '{description}' falhou com código {result.returncode}.")
            logging.error(f"Erro: {result.stderr}")
            
    except Exception as e:
        logging.error(f"Exceção ao executar '{description}': {e}")

def job_solarz_usinas():
    # Caminho relativo a partir de api_assistências
    script = os.path.join("scraper", "solarz_sync_usinas.py")
    if os.path.exists(script):
        run_script(script, "SolarZ Sync Usinas")
    else:
        logging.error(f"Script não encontrado: {script}")

def job_solarz_clientes():
    # Caminho relativo a partir de api_assistências
    script = os.path.join("scraper", "solarz_sync_clientes.py")
    if os.path.exists(script):
        run_script(script, "SolarZ Sync Clientes")
    else:
        logging.error(f"Script não encontrado: {script}")

def run_scheduler():
    logging.info("=== Scheduler Iniciado ===")
    logging.info("Agendando tarefas para rodar a cada 1 hora.")
    
    # Executa uma vez ao iniciar para garantir dados frescos
    job_solarz_clientes()
    job_solarz_usinas()

    # Agendamento
    schedule.every(1).hours.do(job_solarz_clientes)
    schedule.every(1).hours.do(job_solarz_usinas)

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # Garante que o CWD é a raiz do projeto (api_assistências)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run_scheduler()
