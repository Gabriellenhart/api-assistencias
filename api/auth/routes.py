# /api/auth/routes.py

from flask import request, jsonify
# ATUALIZAÇÃO: Importar get_current_user para a rota de refresh
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_current_user
from marshmallow import ValidationError

from . import auth_bp
from flask_jwt_extended import jwt_required, get_current_user # get_current_user já está lá se você implementou o user_lookup
from ..models.usuario import Usuario
from ..schemas.usuario_schema import LoginSchema
from ..schemas.usuario_schema import UsuarioSchema # Importe o schema de saída

import logging
from .. import db


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Endpoint para autenticação de usuário.
    Recebe e-mail e senha, retorna tokens de acesso e refresh em caso de sucesso.
    """
    json_data = request.get_json()
    email_log = json_data.get('email') if isinstance(json_data, dict) else None
    logging.info("Tentativa de login recebida para email=%s", email_log)

    schema = LoginSchema()
    try:
        data = schema.load(json_data)
        email_recebido = data['email']
        senha_recebida = data['password']
        logging.info(f"Dados validados para email: {email_recebido}") # Log 2: Email validado
    except ValidationError as err:
        logging.warning(f"Erro de validação no login: {err.messages}")
        return jsonify({"code": 400, "message": "Dados de entrada inválidos", "errors": err.messages}), 400

    # Busca o usuário pelo e-mail fornecido (case-insensitive pode ser útil aqui, mas vamos manter simples por agora)
    user = Usuario.query.filter(db.func.lower(Usuario.email) == db.func.lower(email_recebido)).first()

    if user:
        logging.info(f"Usuário encontrado no DB: ID={user.id_usuario}, Email={user.email}, Nível={user.nivel}") # Log 3: Usuário encontrado
        # Verifica se a senha está correta
        try:
            password_matches = user.check_password(senha_recebida)
            logging.info("Credenciais conferidas para ID %s", user.id_usuario)

            if password_matches:
                identity = str(user.id_usuario)
                additional_claims = {"nivel": user.nivel}
                access_token = create_access_token(identity=identity, additional_claims=additional_claims)
                refresh_token = create_refresh_token(identity=identity)
                logging.info(f"Login bem-sucedido para ID {user.id_usuario}. Tokens gerados.") # Log 5: Sucesso
                return jsonify({
                    "message": "Login realizado com sucesso!",
                    "access_token": access_token,
                    "refresh_token": refresh_token
                }), 200
            else:
                logging.warning(f"Senha incorreta para o usuário ID {user.id_usuario} (Email: {user.email})") # Log 6a: Senha errada
                return jsonify({"code": 401, "message": "Credenciais inválidas. Verifique seu e-mail e senha."}), 401
        except Exception as e:
            logging.error(f"Erro inesperado durante check_password para ID {user.id_usuario}: {e}", exc_info=True) # Log 6b: Erro no check_password
            return jsonify({"code": 500, "message": "Erro interno ao verificar a senha."}), 500
    else:
        logging.warning(f"Usuário com email '{email_recebido}' não encontrado no banco de dados.") # Log 7: Usuário não encontrado
        return jsonify({"code": 401, "message": "Credenciais inválidas. Verifique seu e-mail e senha."}), 401
    

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Endpoint para renovar um access token.
    O user_lookup_loader já carregou o usuário para nós.
    """
    current_user = get_current_user()
    additional_claims = {"nivel": current_user.nivel}
    
    # CORREÇÃO APLICADA AQUI: Converte o ID inteiro para uma string.
    new_access_token = create_access_token(
        identity=str(current_user.id_usuario), 
        additional_claims=additional_claims
    )
    
    return jsonify({"access_token": new_access_token}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    """Retorna os dados do usuário atualmente autenticado."""
    current_user = get_current_user() # Obtido pelo user_lookup_loader
    return jsonify(UsuarioSchema().dump(current_user)), 200


@auth_bp.route('/me/theme', methods=['PUT'])
@jwt_required()
def update_user_theme():
    """
    Atualiza a preferência de tema do usuário logado.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({"message": "Usuário não encontrado"}), 404
        
    json_data = request.get_json()
    new_theme = json_data.get('theme')

    if new_theme not in ['light', 'dark', 'system']:
        return jsonify({"message": "Valor de tema inválido"}), 400
        
    try:
        current_user.theme_preference = new_theme
        db.session.commit()
        return jsonify({"message": "Preferência de tema atualizada com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao salvar preferência", "error": str(e)}), 500
