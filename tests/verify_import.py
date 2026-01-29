import os
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configuração
load_dotenv()
APP_ENV = os.getenv("APP_ENV", "development")
DB_URI = os.getenv("DEV_DATABASE_URI") if APP_ENV == "development" else os.getenv("DATABASE_URI")

engine = create_engine(DB_URI)

print(f"--- Verificando Importação ({APP_ENV}) ---\n")

with engine.connect() as conn:
    # 1. Verificar contagem de registros com dados da planilha
    result = conn.execute(text("SELECT count(*) FROM usinas WHERE dados_planilha IS NOT NULL"))
    count = result.scalar()
    print(f"Total de Usinas com dados enriquecidos: {count}")
    
    # 2. Pegar uma amostra para exibir
    print("\n--- Amostra de Usina Enriquecida ---")
    result = conn.execute(text("""
        SELECT id_usina, nome_usina, uc, dados_planilha 
        FROM usinas 
        WHERE dados_planilha IS NOT NULL 
        LIMIT 1
    """))
    row = result.fetchone()
    
    if row:
        print(f"ID: {row[0]}")
        print(f"Nome: {row[1]}")
        print(f"UC: {row[2]}")
        print("Dados Extras (JSON):")
        # Pretty print do JSON, limitando caracteres para não poluir
        dados = row[3]
        print(json.dumps(dados, indent=2, ensure_ascii=False)[:1000] + "...")
    else:
        print("Nenhum registro encontrado.")
