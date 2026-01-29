import os
import sys
import json
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from rapidfuzz import process, fuzz
import unicodedata
import re

# Configuração
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(message)s') # Log limpo
logger = logging.getLogger(__name__)

APP_ENV = os.getenv("APP_ENV", "development")
DB_URI = os.getenv("DEV_DATABASE_URI") if APP_ENV == "development" else os.getenv("DATABASE_URI")
engine = create_engine(DB_URI)
Session = sessionmaker(bind=engine)

# Configurações de Deduplicação
SIMILARITY_THRESHOLD = 90 # % de similaridade para considerar duplicata automática
DRY_RUN = True # Se True, não altera o banco, apenas lista o que faria

def normalize_name(name):
    if not name: return ""
    # Remove acentos
    nfkd = unicodedata.normalize('NFKD', name)
    plain = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # Remove pontuação e lowercase
    plain = re.sub(r'[^a-zA-Z0-9 ]', '', plain).lower()
    # Remove termos corporativos comuns que atrapalham fuzzy
    stops = ['ltda', 'sa', 'me', 'eireli', 'comercio', 'servicos', 'de', 'e', 'do', 'da']
    words = [w for w in plain.split() if w not in stops]
    return " ".join(words)

def run_deduplication():
    session = Session()
    try:
        print(f"--- INICIANDO DEDUPLICAÇÃO (Mode: {'SIMULAÇÃO' if DRY_RUN else 'EXECUÇÃO REAL'}) ---")
        print("Este script unifica registros da Planilha (sem ID SolarZ) com registros SolarZ (com ID).\n")

        # 1. Carregar Clientes
        # Separar em dois grupos: Com SolarZ (Alvos) e Sem SolarZ (Candidatos a duplicatas da planilha)
        all_clients = session.execute(text("SELECT id_cliente, nome, solarz_id, dados_planilha FROM clientes")).fetchall()
        
        solarz_clients = []
        planilha_clients = []
        
        for c in all_clients:
            if c.solarz_id is not None:
                solarz_clients.append(c)
            elif c.dados_planilha is not None: # Assumindo que duplicatas vieram da planilha e não tem solarz_id
                planilha_clients.append(c)
        
        print(f"Total Clientes SolarZ (Base): {len(solarz_clients)}")
        print(f"Total Clientes Planilha (Novos): {len(planilha_clients)}")
        
        # Mapa para busca rápida
        # Normalizamos os nomes dos clientes SolarZ para servir de base de busca
        solarz_map = {normalize_name(c.nome): c for c in solarz_clients}
        solarz_names = list(solarz_map.keys())

        merged_counts = 0
        
        # 2. Processar Clientes da Planilha
        for p_client in planilha_clients:
            p_name_norm = normalize_name(p_client.nome)
            
            # Tenta Match Exato ou Fuzzy
            match_name = None
            match_score = 0
            
            # Match 1: Exato (Normalizado)
            if p_name_norm in solarz_map:
                match_name = p_name_norm
                match_score = 100
            else:
                # Match 2: Fuzzy
                extract = process.extractOne(p_name_norm, solarz_names, scorer=fuzz.token_sort_ratio)
                if extract:
                    match_name, match_score, _ = extract

            # Se achou um "pai" compatível
            if match_score >= SIMILARITY_THRESHOLD:
                target_client = solarz_map[match_name]
                
                print(f"[MATCH {match_score}%] Planilha: '{p_client.nome}' ({p_client.id_cliente}) -> SolarZ: '{target_client.nome}' ({target_client.id_cliente})")
                
                if not DRY_RUN:
                    merge_clients(session, target_client, p_client)
                
                merged_counts += 1

        print(f"\n--- Processamento de Clientes Concluído. {merged_counts} merges identificados/realizados. ---")

        # 3. Deduplicação de Usinas (Intra-Cliente)
        # Agora que (teoricamente) movemos clientes, podemos ter usinas duplicadas DENTRO do mesmo cliente (se rodamos o merge acima)
        # OU, se as usinas já estavam associadas a clientes corretos mas duplicadas.
        
        # Vamos varrer TODOS os clientes (agora com as usinas possivelmente agrupadas) e procurar duplicatas internas
        print("\n--- Verificando Duplicidade de Usinas (Mesmo Cliente) ---")
        
        # Pega IDs de todos os clientes (com solarz, que receberam as usinas)
        target_client_ids = [c.id_cliente for c in solarz_clients]
        
        usina_merge_count = 0
        
        for cid in target_client_ids:
            usinas = session.execute(
                text("SELECT id_usina, nome_usina, solarz_id, dados_planilha, uc FROM usinas WHERE id_cliente = :cid"),
                {"cid": cid}
            ).fetchall()
            
            if len(usinas) < 2: continue
            
            # Separa grupos
            u_solarz = [u for u in usinas if u.solarz_id is not None]
            u_planilha = [u for u in usinas if u.solarz_id is None and u.dados_planilha is not None]
            
            if not u_solarz or not u_planilha: continue
            
            # Para cada usina da planilha, tenta achar a correspondente SolarZ DO MESMO CLIENTE
            u_solarz_map = {normalize_name(u.nome_usina): u for u in u_solarz}
            u_solarz_names = list(u_solarz_map.keys())
            
            for up in u_planilha:
                up_name = normalize_name(up.nome_usina)
                
                match = process.extractOne(up_name, u_solarz_names, scorer=fuzz.token_sort_ratio)
                if match and match[1] >= SIMILARITY_THRESHOLD:
                    target_usina = u_solarz_map[match[0]]
                    
                    print(f"  [USINA MATCH] '{up.nome_usina}' -> '{target_usina.nome_usina}' (Cliente {cid})")
                    
                    if not DRY_RUN:
                        merge_usinas(session, target_usina, up)
                    usina_merge_count += 1
        
        print(f"--- Processamento de Usinas Concluído. {usina_merge_count} merges identificados/realizados. ---")

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Erro Crítico: {e}")
    finally:
        session.close()

def merge_clients(session, keep, discard):
    """
    Move tudo do discard para o keep e apaga o discard.
    """
    # 1. Atualizar dados do Keep com dados novos da planilha (sem sobrescrever se já tiver algo importante, mas dados_planilha queremos anexar)
    new_data = discard.dados_planilha
    if new_data:
        # Merge JSON: existing || new
        # No python é mais fácil ler, juntar e gravar
        existing_data = keep.dados_planilha or {}
        # A planilha tem a prioridade de ENRIQUECIMENTO, então adicionamos chaves que não existem ou atualizamos.
        # Como o objetivo é "unificar", vamos fazer update.
        existing_data.update(new_data)
        
        session.execute(
            text("UPDATE clientes SET dados_planilha = :data WHERE id_cliente = :kid"),
            {"data": json.dumps(existing_data), "kid": keep.id_cliente}
        )

    # 2. Mover Usinas
    session.execute(
        text("UPDATE usinas SET id_cliente = :kid WHERE id_cliente = :did"),
        {"kid": keep.id_cliente, "did": discard.id_cliente}
    )
    
    # 3. Mover Chamados (se houver)
    session.execute(
        text("UPDATE chamados SET id_cliente = :kid WHERE id_cliente = :did"),
        {"kid": keep.id_cliente, "did": discard.id_cliente}
    )

    # 4. Deletar Cliente Duplicado
    session.execute(
        text("DELETE FROM clientes WHERE id_cliente = :did"),
        {"did": discard.id_cliente}
    )

def merge_usinas(session, keep, discard):
    """
    Funde usina discard na usina keep.
    """
    # 1. Dados Planilha
    if discard.dados_planilha:
        existing_data = keep.dados_planilha or {}
        existing_data.update(discard.dados_planilha)
        
        # 2. UC (Se o keep não tem e o discard tem, pegamos)
        new_uc = keep.uc
def merge_usinas(session, keep, discard):
    """
    Funde usina discard na usina keep.
    """
    # 1. Dados Planilha & UC
    if discard.dados_planilha or discard.uc:
        existing_data = keep.dados_planilha or {}
        if discard.dados_planilha:
            existing_data.update(discard.dados_planilha)
        
        new_uc = keep.uc
        if not new_uc and discard.uc:
            new_uc = discard.uc
            
        # Tenta update SEGURO (JSON + UC se possível, senão só JSON)
        # Usamos savepoint para não abortar a transação inteira em caso de erro de UNIQUE
        try:
            session.begin_nested() 
            session.execute(
                text("UPDATE usinas SET dados_planilha = :data, uc = :uc WHERE id_usina = :kid"),
                {"data": json.dumps(existing_data), "uc": new_uc, "kid": keep.id_usina}
            )
            session.commit() # Commit savepoint
        except Exception:
            session.rollback() # Rollback to savepoint
            # Tenta só JSON (ignorando UC conflituoso)
            session.execute(
                 text("UPDATE usinas SET dados_planilha = :data WHERE id_usina = :kid"),
                 {"data": json.dumps(existing_data), "kid": keep.id_usina}
            )
        
    # 2. Mover Chamados (se houver, improvável mas seguro)
    session.execute(
        text("UPDATE chamados SET id_usina = :kid WHERE id_usina = :did"),
        {"kid": keep.id_usina, "did": discard.id_usina}
    )
    
    # 3. Deletar Usina Duplicada
    session.execute(
        text("DELETE FROM usinas WHERE id_usina = :did"),
        {"did": discard.id_usina}
    )

if __name__ == "__main__":
    # Verifica argumento para rodar de verdade
    if len(sys.argv) > 1 and sys.argv[1] == "--confirm":
        DRY_RUN = False
    
    run_deduplication()
