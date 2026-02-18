import os
import sys
from api import create_app, db
from api.models.usuario import Usuario

app = create_app(os.getenv('FLASK_ENV', 'production'))

def reset_password():
    print("--- RESET PASSWORD ---")
    
    with app.app_context():
        email = input("Digite o e-mail do usuário admin: ").strip()
        user = Usuario.query.filter_by(email=email).first()
        
        if not user:
            print(f"[ERRO] Usuário com email '{email}' não encontrado.")
            return

        new_pass = input(f"Digite a nova senha para {user.nome_usuario}: ").strip()
        
        if not new_pass:
            print("[ERRO] Senha não pode ser vazia.")
            return

        try:
            # A atribuição .password aciona o setter que faz o hash automaticamente
            user.password = new_pass 
            db.session.commit()
            print(f"[SUCESSO] Senha atualizada para o usuário ID {user.id_usuario}.")
        except Exception as e:
            db.session.rollback()
            print(f"[ERRO] Falha ao atualizar senha: {e}")

if __name__ == "__main__":
    reset_password()
