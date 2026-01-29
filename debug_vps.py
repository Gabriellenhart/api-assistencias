import os
from api import create_app, db
from api.models.usuario import Usuario
from sqlalchemy import text

app = create_app(os.getenv('FLASK_ENV', 'production'))

with app.app_context():
    print("--- DIAGNOSTICO DE VPS ---")
    try:
        # 1. Testar conexao
        db.session.execute(text('SELECT 1'))
        print("[OK] Conexão com banco de dados bem-sucedida.")
    except Exception as e:
        print(f"[ERRO] Falha ao conectar no banco: {e}")
        exit(1)

    # 2. Verificar Tabela
    try:
        users = Usuario.query.all()
        print(f"[OK] Tabela 'usuarios' acessada. Total de usuários: {len(users)}")
        
        if len(users) == 0:
            print("[AVISO] Nenhum usuário encontrado. Você precisa criar um admin.")
            print("Execute o comando: flask create-admin")
        else:
            for u in users:
                print(f" - ID: {u.id_usuario} | User: {u.nome_usuario} | Email: {u.email} | Nivel: {u.nivel}")
                if not u.password_hash:
                    print(f"   [ALERTA] Usuário {u.email} sem hash de senha!")
    except Exception as e:
        print(f"[ERRO] Falha ao consultar tabela de usuários: {e}")
        print("Provavelmente precisa rodar: flask db upgrade")
