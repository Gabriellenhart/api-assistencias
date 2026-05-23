import logging
import os
import subprocess
import sys
import time

import schedule

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Scheduler] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scheduler.log'),
    ],
)


def run_script(script_path, description):
    logging.info("Iniciando tarefa: %s", description)
    try:
        cmd = [sys.executable, script_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            logging.info("Tarefa '%s' concluida com sucesso.", description)
        else:
            logging.error("Tarefa '%s' falhou com codigo %s.", description, result.returncode)
            logging.error("Erro: %s", result.stderr)
    except Exception as exc:
        logging.error("Excecao ao executar '%s': %s", description, exc)


def job_solarz_usinas():
    script = os.path.join('scraper', 'solarz_sync_usinas.py')
    if os.path.exists(script):
        run_script(script, 'SolarZ Sync Usinas')
    else:
        logging.error('Script nao encontrado: %s', script)


def job_solarz_clientes():
    script = os.path.join('scraper', 'solarz_sync_clientes.py')
    if os.path.exists(script):
        run_script(script, 'SolarZ Sync Clientes')
    else:
        logging.error('Script nao encontrado: %s', script)


def run_scheduler():
    logging.info('=== Scheduler Iniciado ===')
    logging.info('Agendando tarefas para rodar a cada 1 hora.')

    job_solarz_clientes()
    job_solarz_usinas()

    schedule.every(1).hours.do(job_solarz_clientes)
    schedule.every(1).hours.do(job_solarz_usinas)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    # Ensure cwd is the project root.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run_scheduler()
