"""
solarz_sync_usinas.py
---------------------
Script de sincronização que utiliza a lógica validada de autenticação e scraping
do projeto de referência, integrado ao backend API-Assistências para persistência.

Execução:
  python -m api_assistências.scraper.solarz_sync_usinas
"""

import asyncio
import logging
import os
import re
import sys
from typing import Any, Dict, List

import httpx
from dateutil.parser import isoparse
from tenacity import retry, stop_after_attempt, wait_exponential

# Adiciona o diretório pai ao path para importar 'api' se rodado como script solto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from api import create_app
from api.services.solarz_service import processar_sincronizacao_solarz

# ---------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------
# Credenciais conforme editado pelo usuário anteriormente
SOLARZ_BASE_URL = os.getenv("SOLARZ_BASE_URL", "https://app.solarz.com.br")
SOLARZ_USERNAME = os.getenv("SOLARZ_USERNAME", "monitoramento@e-gera.com.br")
SOLARZ_PASSWORD = os.getenv("SOLARZ_PASSWORD", "egera100")

DASHBOARD_FILTER_PATH = "/api-sz/usinas/dashboard/filter"
DEFAULT_FILTER_PAYLOAD = {
    "monitored": True,
    "sortOrder": "desc",
    "sortBy": "installationDate",
    "page": 0,
    "pageSize": 100,
}

# ---------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("solarz_sync")

# ---------------------------------------------------------------------
# 1. AUTENTICAÇÃO (Lógica adaptada de auth.py)
# ---------------------------------------------------------------------
async def obter_token_autenticado() -> str:
    """
    Autentica no sistema SolarZ e obtém um token de acesso via Regex no HTML do dashboard.
    """
    if not SOLARZ_USERNAME or not SOLARZ_PASSWORD:
        raise RuntimeError("Credenciais SOLARZ não definidas.")

    async with httpx.AsyncClient(
        base_url=SOLARZ_BASE_URL,
        timeout=20, # Aumentado para segurança
        follow_redirects=True,
    ) as client:
        # 1. Login inicial (GET) para cookies
        logger.info("Acessando página de login...")
        resp = await client.get("/login")
        resp.raise_for_status()

        # 2. Login (POST)
        logger.info("Enviando credenciais...")
        creds = {
            "username": SOLARZ_USERNAME,
            "password": SOLARZ_PASSWORD,
        }
        resp = await client.post("/login", 
            data=creds,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        resp.raise_for_status()

        # 3. Extrair token do Dashboard
        logger.info("Acessando dashboard para extrair token...")
        resp = await client.get("/integrador/dashboard/v3")
        resp.raise_for_status()
        
        html = resp.text
        token_match = re.search(r'const token = "(.*?)"', html)
        if not token_match:
            # Fallback de debug: imprime parte do HTML se falhar
            logger.error("HTML recebido sem token (primeiros 500 chars): " + html[:500])
            raise RuntimeError("Token SolarZ não encontrado no HTML")

        token = token_match.group(1)
        # logger.info(f"Token obtido: {token[:10]}...")
        return token

# ---------------------------------------------------------------------
# 2. SCRAPING (Lógica adaptada de synchronizer_performance.py)
# ---------------------------------------------------------------------
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1))
async def fetch_dashboard(monitored: bool) -> List[Dict[str, Any]]:
    """
    Busca os dados do dashboard de usinas da SolarZ, com retentativa.
    Paginação automática.
    """
    try:
        token = await obter_token_autenticado()
    except Exception as e:
        logger.error(f"Erro fatal na autenticação: {e}")
        raise e

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://pages.solarz.com.br",
        "Referer": "https://pages.solarz.com.br/",
    }

    async with httpx.AsyncClient(
        base_url=SOLARZ_BASE_URL,
        timeout=20, # Timeout relaxado
        follow_redirects=True,
        headers=headers,
    ) as client:
        todas = []
        page = 0
        
        while True:
            logger.info(f"Buscando página {page} (monitored={monitored})...")
            payload = {
                **DEFAULT_FILTER_PAYLOAD,
                "monitored": monitored,
                "page": page
            }
            
            resp = await client.post(DASHBOARD_FILTER_PATH, json=payload)
            resp.raise_for_status()
            
            data = resp.json()
            # O código de referência acessa .get("plants", {}).get("content", [])
            chunk = data.get("plants", {}).get("content", [])
            
            if not chunk:
                break
                
            todas.extend(chunk)
            page += 1
            
        logger.info(f"Total de usinas com monitored={monitored}: {len(todas)}")
        return todas

# ---------------------------------------------------------------------
# 3. ORQUESTRAÇÃO E PERSISTÊNCIA
# ---------------------------------------------------------------------
async def run_sync_logic():
    logger.info("=== Iniciando Sincronização SolarZ (Scraper + Backend) ===")
    
    try:
        # 1. Scraping dos dados (Async)
        logger.info("Baixando usinas Monitoradas...")
        monitoradas = await fetch_dashboard(monitored=True)
        
        logger.info("Baixando usinas Não Monitoradas...")
        nao_monitoradas = await fetch_dashboard(monitored=False)
        
        todas_usinas = monitoradas + nao_monitoradas
        logger.info(f"Total de usinas capturadas: {len(todas_usinas)}")
        
        if not todas_usinas:
            logger.warning("Nenhuma usina encontrada para processar.")
            return

        # 2. Persistência (Sync via Flask Context)
        logger.info("Enviando para o serviço de persistência do backend...")
        
        # Cria contexto da aplicação Flask para ter acesso ao DB configurado
        app = create_app('default')
        
        with app.app_context():
            # Usa o serviço oficial que já lida com as regras de negócio
            # Note que processar_sincronizacao_solarz é síncrono (SQLAlchemy sync)
            stats = processar_sincronizacao_solarz(todas_usinas)
            
            logger.info("=== Sincronização Concluída ===")
            logger.info(f"Processadas: {stats['total_lidas']}")
            logger.info(f"Novas: {stats['novas']}")
            logger.info(f"Atualizadas: {stats['atualizadas']}")
            logger.info(f"Erros: {stats['erros']}")

    except Exception as e:
        logger.error(f"Erro crítico na execução do script: {e}", exc_info=True)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_sync_logic())
