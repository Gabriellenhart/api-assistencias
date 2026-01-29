"""
solarz_sync_clientes.py
-----------------------
Script scraper para sincronizar Clientes da SolarZ com o backend.
Baseado na estrutura validada do scraper de usinas.

Execução:
  python -m api_assistências.scraper.solarz_sync_clientes
  (requer variáveis de ambiente configuradas ou hardcoded abaixo para teste)
"""

import asyncio
import logging
import os
import re
import sys
from typing import Any, Dict, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

# Adiciona diretório pai ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from api import create_app
from api.services.solarz_service import processar_sincronizacao_clientes

# ---------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------
SOLARZ_BASE_URL = os.getenv("SOLARZ_BASE_URL", "https://app.solarz.com.br")
SOLARZ_USERNAME = os.getenv("SOLARZ_USERNAME", "monitoramento@e-gera.com.br")
SOLARZ_PASSWORD = os.getenv("SOLARZ_PASSWORD", "egera100")
SOLARZ_PAGE_SIZE = int(os.getenv("SOLARZ_PAGE_SIZE", "100"))

# Rota para buscar clientes (baseado no script do usuário)
# Endpoint parece ser: /api-sz/clientes/page/0?pageSize=100
CLIENTES_ENDPOINT_TEMPLATE = "/api-sz/clientes/page/{page}"

# ---------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("solarz_clientes_sync")

# ---------------------------------------------------------------------
# 1. AUTENTICAÇÃO (Reuso da lógica validada)
# ---------------------------------------------------------------------
async def obter_token_autenticado() -> str:
    if not SOLARZ_USERNAME or not SOLARZ_PASSWORD:
        raise RuntimeError("Credenciais SOLARZ não definidas.")

    async with httpx.AsyncClient(
        base_url=SOLARZ_BASE_URL,
        timeout=25,
        follow_redirects=True,
    ) as client:
        # 1. Login inicial
        logger.info("Autenticando - Passo 1 (Cookies)...")
        resp = await client.get("/login")
        resp.raise_for_status()

        # 2. Login POST
        logger.info("Autenticando - Passo 2 (Credenciais)...")
        creds = {"username": SOLARZ_USERNAME, "password": SOLARZ_PASSWORD}
        resp = await client.post("/login", 
            data=creds,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        resp.raise_for_status()

        # 3. Extrair Token
        logger.info("Autenticando - Passo 3 (Token)...")
        resp = await client.get("/integrador/dashboard/v3")
        resp.raise_for_status()
        
        m = re.search(r'const token = "(.*?)"', resp.text)
        if not m:
            logger.error("Falha ao extrair token do HTML.")
            raise RuntimeError("Token SolarZ não encontrado.")
        
        return m.group(1)

# ---------------------------------------------------------------------
# 2. FETCH CLIENTES
# ---------------------------------------------------------------------
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1))
async def fetch_clientes_page(client: httpx.AsyncClient, page: int) -> Dict[str, Any]:
    url = CLIENTES_ENDPOINT_TEMPLATE.format(page=page)
    logger.info(f"Buscando página {page} via POST...")
    
    # Tentativa com POST e payload de paginação
    payload = {
        "page": page,
        "pageSize": SOLARZ_PAGE_SIZE
    }
    
    resp = await client.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()

async def fetch_all_clientes() -> List[Dict[str, Any]]:
    try:
        token = await obter_token_autenticado()
    except Exception as e:
        logger.error(f"Erro fatal na autenticação: {e}")
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Origin": "https://pages.solarz.com.br", # Manter compatibilidade com headers originais se necessário
        "Referer": "https://pages.solarz.com.br/",
    }

    async with httpx.AsyncClient(
        base_url=SOLARZ_BASE_URL,
        timeout=30,
        follow_redirects=True,
        headers=headers,
    ) as client:
        all_items = []
        page = 0
        
        while True:
            data = await fetch_clientes_page(client, page)
            
            # Tenta extrair conteúdo de diferentes estruturas comuns
            content = data.get("content", [])
            if not content:
                # Fallback: result.content
                content = (data.get("result") or {}).get("content", []) or []
                
            if not content:
                break
                
            all_items.extend(content)
            
            # Paginação inteligente
            total_pages = data.get("totalPages") or (data.get("result") or {}).get("totalPages")
            
            if total_pages is not None:
                page += 1
                if page >= int(total_pages):
                    break
            else:
                # Se não tem totalPages, para se vier menos que o tamanho da página
                if len(content) < SOLARZ_PAGE_SIZE:
                    break
                page += 1
                
        logger.info(f"Total de clientes extraídos: {len(all_items)}")
        return all_items

# ---------------------------------------------------------------------
# 3. ORQUESTRAÇÃO
# ---------------------------------------------------------------------
async def run_sync_logic():
    logger.info("=== Sincronização de Clientes SolarZ ===")
    
    # Busca dados
    lista_clientes = await fetch_all_clientes()
    
    if not lista_clientes:
        logger.warning("Nenhum cliente encontrado ou erro na busca.")
        return

    # Persistência
    logger.info("Persistindo dados no backend...")
    app = create_app('default')
    
    with app.app_context():
        try:
            stats = processar_sincronizacao_clientes(lista_clientes)
            logger.info("=== Concluído ===")
            logger.info(f"Total: {stats['total_lidas']}")
            logger.info(f"Novos: {stats['novas']}")
            logger.info(f"Atualizados: {stats['atualizadas']}")
            logger.info(f"Erros: {stats['erros']}")
        except Exception as e:
            logger.error(f"Erro na persistência: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_sync_logic())
