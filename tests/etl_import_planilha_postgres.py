import os
import sys
import uuid
import json
import logging
import unicodedata
import re
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from rapidfuzz import process, fuzz
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# --- CONFIGURAÇÃO ---
load_dotenv()

# Setup Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ambiente e Conexão
APP_ENV = os.getenv("APP_ENV", "development")
DB_URI = os.getenv("DEV_DATABASE_URI") if APP_ENV == "development" else os.getenv("DATABASE_URI")

if not DB_URI:
    logger.error("DATABASE_URI não definida. Verifique suas variáveis de ambiente.")
    sys.exit(1)

engine = create_engine(DB_URI)
Session = sessionmaker(bind=engine)

# Caminho do Arquivo
FILE_PATH = os.path.join(os.path.dirname(__file__), 'tests', 'Controle Geral (1).ods')

# --- FUNÇÕES DE AJUDA (NORMALIZAÇÃO) ---

def normalize_text(text_val):
    if not isinstance(text_val, str):
        return ""
    # Remove acentos e converte para maiúsculas
    nfkd_form = unicodedata.normalize('NFKD', text_val)
    text_val = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Remove caracteres não alfanuméricos (mantém espaços)
    text_val = re.sub(r'[^A-Z0-9 ]', '', text_val.upper())
    # Colapsa espaços
    return " ".join(text_val.split())

def extract_cliente_from_usina(usina_nome):
    """
    Remove sufixos comuns de nomes de usina para tentar descobrir o nome do cliente.
    """
    if not usina_nome:
        return ""
    
    canon = normalize_text(usina_nome)
    
    # Lista de sufixos/termos a remover
    stopwords = [
        "AMPLIACAO", "EXPANSAO", "UPGRADE", "USINA", "UFV", "SOLAR", 
        "MICROGERACAO", "MINIGERACAO", "ANEXO", "B"
    ]
    
    # Remove números isolados no fim (ex: "JORGE 2")
    canon = re.sub(r' \d+$', '', canon)
    
    # Remove stopwords
    words = canon.split()
    filtered = [w for w in words if w not in stopwords]
    
    return " ".join(filtered)

def normalize_uc(uc_val):
    """Mantém apenas dígitos da UC."""
    if pd.isna(uc_val) or uc_val == "":
        return None
    s = str(uc_val)
    digits = re.sub(r'\D', '', s)
    return digits if digits else None

# --- CORE: IMPORTAÇÃO ---

def run_import():
    session = Session()
    try:
        if not os.path.exists(FILE_PATH):
            raise FileNotFoundError(f"Arquivo não encontrado: {FILE_PATH}")

        # 1. Cria Batch
        batch_id = str(uuid.uuid4())
        logger.info(f"Iniciando Batch: {batch_id}")
        
        session.execute(
            text("INSERT INTO import_batches (batch_id, source_file, notes) VALUES (:bid, :src, :note)"),
            {"bid": batch_id, "src": FILE_PATH, "note": "Importação via ETL Script"}
        )
        
        # 2. Carrega Planilha
        logger.info("Lendo planilha ODS...")
        df = pd.read_excel(FILE_PATH, engine="odf")
        
        # Adiciona colunas normalizadas ao DF
        df['usina_norm'] = df['CLIENTE'].apply(normalize_text) # CLIENTE na planilha é USINA
        df['cliente_estimado'] = df['CLIENTE'].apply(extract_cliente_from_usina)
        df['uc_norm'] = df['UC'].apply(normalize_uc)
        
        # 3. Carrega Clientes Existentes para Memória (para Fuzzy Match)
        logger.info("Carregando clientes existentes...")
        existing_clients = pd.read_sql("SELECT id_cliente, nome, dados_planilha FROM clientes", engine)
        existing_clients['nome_norm'] = existing_clients['nome'].apply(normalize_text)
        
        # Dicionário para acesso rápido e cache de novos criados neste batch
        client_map = {row['nome_norm']: row['id_cliente'] for _, row in existing_clients.iterrows()}
        new_clients_cache = {} # nome_norm -> id_cliente (criados agora)

        # 4. Processa Linhas
        logger.info(f"Processando {len(df)} linhas...")
        
        count_updates = 0
        count_inserts = 0
        
        for idx, row in df.iterrows():
            raw_usina_name = row['CLIENTE'] # Nome da Usina na Planilha
            cliente_canon = row['cliente_estimado']
            uc_target = row['uc_norm']
            cidade = row.get('LOCAL INSTALAÇÃO', '')
            
            if not cliente_canon:
                continue

            # --- A. Identificar ou Criar Cliente ---
            
            # Tenta match exato
            cliente_id = client_map.get(cliente_canon) or new_clients_cache.get(cliente_canon)
            
            # Match Fuzzy se não achou exato
            if not cliente_id:
                # Procura nas chaves existentes
                choices = list(client_map.keys())
                match = process.extractOne(cliente_canon, choices, scorer=fuzz.token_sort_ratio)
                
                if match and match[1] >= 90: # Alta confiança
                    cliente_id = client_map[match[0]]
                    logger.info(f"Fuzzy Match: '{cliente_canon}' -> '{match[0]}' (ID: {cliente_id})")
            
            # Se ainda não existe, cria CLIENTE
            if not cliente_id:
                logger.info(f"Criando novo cliente: {cliente_canon}")
                
                # Prepara dados do cliente (telefone, etc)
                dados_extra = {
                    "historico": [{
                        "batch_id": batch_id,
                        "data_import": datetime.now().isoformat(),
                        "origem": "planilha_ods",
                        "linha": idx + 1
                    }]
                }
                
                # Insert Cliente
                res = session.execute(
                    text("""
                        INSERT INTO clientes (nome, contato_telefone, dados_planilha) 
                        VALUES (:nome, :tel, :dados) 
                        RETURNING id_cliente
                    """),
                    {
                        "nome": raw_usina_name, # Usando o nome raw da usina como nome do cliente inicialmente se não tiver outro
                        # O ideal seria usar o cliente_canon formatado bonitinho, mas vamos usar o raw limpo
                        # Ajuste: Vamos usar o cliente_canon Capitalized para ficar bonito
                        "nome": cliente_canon.title(),
                        "tel": str(row.get('Telefone', ''))[:50],
                        "dados": json.dumps(dados_extra)
                    }
                )
                cliente_id = res.fetchone()[0]
                
                # Registra Insert
                session.execute(
                    text("INSERT INTO import_inserts (batch_id, table_name, row_id) VALUES (:bid, 'clientes', :rid)"),
                    {"bid": batch_id, "rid": cliente_id}
                )
                
                # Atualiza cache
                new_clients_cache[cliente_canon] = cliente_id
            
            # --- B. Identificar ou Criar Usina (UPSERT/LOGIC) ---
            
            usina_dados_extra = row.to_dict()
            # Converte valores não serializáveis
            for k, v in usina_dados_extra.items():
                if pd.isna(v): usina_dados_extra[k] = None
                elif isinstance(v, (datetime, pd.Timestamp)): usina_dados_extra[k] = v.isoformat()
            
            usina_dados_json = {
                "origem": "planilha_ods",
                "dados_brutos": usina_dados_extra,
                "batch_id": batch_id
            }

            # Lógica para encontrar Usina
            usina_id = None
            
            # 1. Busca por UC (Fortíssima)
            if uc_target:
                res = session.execute(
                    text("SELECT id_usina, dados_planilha FROM usinas WHERE id_cliente = :cid AND uc = :uc"),
                    {"cid": cliente_id, "uc": uc_target}
                )
                existing_usina = res.fetchone()
                
                if existing_usina:
                    usina_id = existing_usina[0]
                    # Backup antes do UPDATE
                    session.execute(
                        text("""
                            INSERT INTO import_usinas_backup (batch_id, id_usina, before_row, action)
                            VALUES (:bid, :uid, :before, 'UPDATE')
                            ON CONFLICT (batch_id, id_usina) DO NOTHING
                        """),
                        {"bid": batch_id, "uid": usina_id, "before": json.dumps({"dados_planilha": existing_usina[1]})}
                    )
            
            # 2. Busca por Contexto (Sem UC, mas é ampliação)
            # "Só tenta “colar” se for ampliação e existir exatamente 1 usina do cliente naquela cidade"
            elif 'AMPLIACAO' in normalize_text(raw_usina_name):
                # Busca usinas desse cliente na mesma cidade
                # *Assumindo que temos cidade na usina, mas vamos usar filtro genérico por enquanto
                # Se a coluna 'cidade' na tabela usina existir e estiver preenchida, usamos.
                # Caso contrário, confiamos apenas na unicidade de 'cliente' se ele tiver só 1 usina.
                
                res = session.execute(
                    text("SELECT id_usina FROM usinas WHERE id_cliente = :cid"),
                    {"cid": cliente_id}
                )
                usinas_do_cliente = res.fetchall()
                
                if len(usinas_do_cliente) == 1:
                     usina_id = usinas_do_cliente[0][0]
                     # Backup executado abaixo no bloco de update se fosse necessário, mas aqui
                     # talvez a gente só queira anexar o dado novo na lista de 'historico' do jsonb
                     # sem alterar colunas estruturais.
            
            
            # --- C. Executar Upsert/Insert Usina ---
            
            if usina_id:
                # UPDATE (Enriquecimento)
                # Adiciona ao json de dados_planilha
                session.execute(
                    text("""
                        UPDATE usinas 
                        SET dados_planilha = coalesce(dados_planilha, '{}'::jsonb) || :new_data 
                        WHERE id_usina = :uid
                    """),
                    {"new_data": json.dumps(usina_dados_json), "uid": usina_id}
                )
                count_updates += 1
                
            else:
                # INSERT (Nova Usina)
                res = session.execute(
                    text("""
                        INSERT INTO usinas (id_cliente, nome_usina, uc, cidade, dados_planilha)
                        VALUES (:cid, :nome, :uc, :cidade, :dados)
                        RETURNING id_usina
                    """),
                    {
                        "cid": cliente_id,
                        "nome": raw_usina_name,
                        "uc": uc_target,
                        "cidade": str(cidade)[:100] if cidade else None,
                        "dados": json.dumps(usina_dados_json)
                    }
                )
                usina_id = res.fetchone()[0]
                
                session.execute(
                    text("INSERT INTO import_inserts (batch_id, table_name, row_id) VALUES (:bid, 'usinas', :rid)"),
                    {"bid": batch_id, "rid": usina_id}
                )
                count_inserts += 1

        session.commit()
        logger.info(f"IMPORT OK. batch_id = {batch_id}")
        logger.info(f"Resumo: {count_updates} updates, {count_inserts} inserts.")
        return batch_id

    except Exception as e:
        session.rollback()
        logger.error(f"Erro crítico na importação: {e}")
        raise
    finally:
        session.close()

# --- ROLLBACK ---

def rollback_batch(batch_id):
    session = Session()
    try:
        logger.info(f"Iniciando Rollback do Batch: {batch_id}")
        
        # 1. Valida Batch
        res = session.execute(text("SELECT batch_id FROM import_batches WHERE batch_id = :bid"), {"bid": batch_id})
        if not res.fetchone():
            logger.error("Batch não encontrado.")
            return

        # 2. Desfazer Updates (Restaurar Snapshots)
        # Clientes
        logger.info("Revertendo Updates em Clientes...")
        backups_clientes = session.execute(
            text("SELECT id_cliente, before_row FROM import_clientes_backup WHERE batch_id = :bid"),
            {"bid": batch_id}
        ).fetchall()
        
        for row in backups_clientes:
            # Restaura json dados_planilha original
            before = row[1]
            if 'dados_planilha' in before:
                session.execute(
                    text("UPDATE clientes SET dados_planilha = :data WHERE id_cliente = :id"),
                    {"data": json.dumps(before['dados_planilha']), "id": row[0]}
                )

        # Usinas
        logger.info("Revertendo Updates em Usinas...")
        backups_usinas = session.execute(
            text("SELECT id_usina, before_row FROM import_usinas_backup WHERE batch_id = :bid"),
            {"bid": batch_id}
        ).fetchall()
        
        for row in backups_usinas:
            before = row[1]
            if 'dados_planilha' in before:
                session.execute(
                    text("UPDATE usinas SET dados_planilha = :data WHERE id_usina = :id"),
                    {"data": json.dumps(before['dados_planilha']), "id": row[0]}
                )

        # 3. Apagar Inserts (Ordem: Usinas -> Clientes por causa da FK)
        logger.info("Apagando registros criados...")
        
        # Usinas criadas
        session.execute(
            text("""
                DELETE FROM usinas 
                WHERE id_usina IN (
                    SELECT row_id FROM import_inserts 
                    WHERE batch_id = :bid AND table_name = 'usinas'
                )
            """),
            {"bid": batch_id}
        )
        
        # Clientes criados (pode falhar se tiverem outras dependências criadas fora do batch, mas o script assume janela controlada)
        session.execute(
            text("""
                DELETE FROM clientes 
                WHERE id_cliente IN (
                    SELECT row_id FROM import_inserts 
                    WHERE batch_id = :bid AND table_name = 'clientes'
                )
            """),
            {"bid": batch_id}
        )

        # 4. Remove Batch (Cascade limpa logs)
        session.execute(text("DELETE FROM import_batches WHERE batch_id = :bid"), {"bid": batch_id})
        
        session.commit()
        logger.info("ROLLBACK CONCLUÍDO COM SUCESSO.")

    except Exception as e:
        session.rollback()
        logger.error(f"Erro no rollback: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    mode = os.getenv("MODE", "import").lower()
    
    if mode == "rollback":
        bid = os.getenv("BATCH_ID")
        if not bid:
            logger.error("Para rollback, defina a env var BATCH_ID")
        else:
            rollback_batch(bid)
    else:
        run_import()
