import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Carrega variáveis de ambiente
load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development")
DB_URI = os.getenv("DEV_DATABASE_URI") if APP_ENV == "development" else os.getenv("DATABASE_URI")

if not DB_URI:
    print("Erro: DATABASE_URI não configurada no .env")
    sys.exit(1)

print(f"Conectando ao banco ({APP_ENV})...")
engine = create_engine(DB_URI)

sql_file = 'etl_db_setup.sql'

try:
    with engine.connect() as conn:
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_commands = f.read()
            # PostgreSQL suporta execução de multiplos comandos em um bloco, 
            # mas sqlalchemy pode preferir commit explícito.
            conn.execute(text(sql_commands))
            conn.commit()
            
    print("Sucesso! DDL aplicado com sucesso.")
    print("Tabelas de batch e novas colunas criadas.")
    
except Exception as e:
    print(f"Erro ao aplicar DDL: {e}")
