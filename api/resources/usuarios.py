# /api/resources/usuarios.py (VERSÃO FINAL E CORRIGIDA)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_ # Importa o 'or_'
import logging
import traceback
import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

from .. import db
from ..models import Usuario
from ..schemas.usuario_schema import UsuarioSchema, UsuarioInputSchema
# Importa TODOS os decorators necessários
from ..decorators import admin_required, tecnico_required, supervisor_or_admin_required 

# Helper para checar permissão (pode ir para decorators.py no futuro)
def check_permission(current_user_level, current_user_id_str, target_user_id):
    """Verifica se o usuário atual tem permissão para gerenciar o usuário alvo."""
    target_user_id_str = str(target_user_id)
    
    # Usuário pode sempre editar a si mesmo
    if current_user_id_str == target_user_id_str:
        return True
        
    # Admin pode editar qualquer um
    if current_user_level == 'admin':
        return True
        
    # Supervisor pode editar a si mesmo (já coberto) ou técnicos
    if current_user_level == 'supervisor':
        target_user = Usuario.query.get(target_user_id)
        if target_user and target_user.nivel == 'tecnico':
            return True
            
    return False

# Função allowed_file (para upload de avatar)
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


usuarios_bp = Blueprint('usuarios', __name__)

# --- ROTAS CRUD ---

@usuarios_bp.route('', methods=['POST'])
@jwt_required()
@admin_required() # Somente Admin pode criar usuários
def criar_usuario():
    json_data = request.get_json()
    schema = UsuarioInputSchema()
    try: data = schema.load(json_data)
    except ValidationError as err: return jsonify({"message": "Erro de validação", "errors": err.messages}), 400
    if Usuario.query.filter_by(email=data['email']).first(): return jsonify({"message": "Este e-mail já está em uso."}), 409
    novo_usuario = Usuario(nome_usuario=data['nome_usuario'], email=data['email'], nivel=data['nivel'])
    novo_usuario.password = data['password']
    try:
        db.session.add(novo_usuario)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"ERRO AO SALVAR NOVO USUARIO: {e}\n{traceback.format_exc()}") 
        return jsonify({"message": "Erro ao salvar usuário no banco de dados", "error": str(e)}), 500
    return jsonify(UsuarioSchema().dump(novo_usuario)), 201


@usuarios_bp.route('', methods=['GET'])
@jwt_required()
@supervisor_or_admin_required() # Permite que Admin e Supervisor acessem
def listar_usuarios():
    """
    Lista usuários com base no nível do solicitante.
    - Admin: Vê todos.
    - Supervisor: Vê a si mesmo e todos os técnicos.
    """
    claims = get_jwt()
    current_user_level = claims.get('nivel')
    current_user_id = int(get_jwt_identity())

    query = Usuario.query

    if current_user_level == 'supervisor':
        # Filtra para incluir apenas técnicos OU o próprio supervisor
        query = query.filter(
            or_(
                Usuario.nivel == 'tecnico',
                Usuario.id_usuario == current_user_id
            )
        )
    
    usuarios = query.order_by(Usuario.nome_usuario).all()
    return jsonify(UsuarioSchema(many=True).dump(usuarios))


@usuarios_bp.route('/<int:id_usuario>', methods=['GET'])
@jwt_required()
def detalhar_usuario(id_usuario): # <-- SÓ UMA DEFINIÇÃO DESTA FUNÇÃO
    """
    Detalha um usuário. Um usuário só pode ver detalhes de quem
    ele tem permissão para gerenciar (ou de si mesmo).
    """
    current_user_id_str = get_jwt_identity()
    claims = get_jwt()
    current_user_level = claims.get('nivel')
    
    if not check_permission(current_user_level, current_user_id_str, id_usuario):
         return jsonify({"message": "Você não tem permissão para ver este usuário."}), 403

    usuario = Usuario.query.get_or_404(id_usuario)
    return jsonify(UsuarioSchema().dump(usuario))


@usuarios_bp.route('/<int:id_usuario>', methods=['PUT'])
@jwt_required()
def atualizar_usuario(id_usuario):
    """Atualiza um usuário com base na hierarquia de permissões."""
    current_user_id_str = get_jwt_identity()
    claims = get_jwt()
    current_user_level = claims.get('nivel')
    target_user = Usuario.query.get_or_404(id_usuario)
    
    if not check_permission(current_user_level, current_user_id_str, id_usuario):
         return jsonify({"message": "Você não tem permissão para editar este usuário."}), 403

    json_data = request.get_json()
    
    allowed_fields_to_edit = ['nome_usuario', 'email', 'password']
    is_editing_self = (current_user_id_str == str(id_usuario))

    if current_user_level == 'admin' and not is_editing_self:
         allowed_fields_to_edit.append('nivel')
    
    schema = UsuarioInputSchema(partial=True, exclude=[f for f in UsuarioInputSchema().fields if f not in allowed_fields_to_edit])
    
    try:
        data = schema.load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400

    if 'email' in data and data['email'] != target_user.email and Usuario.query.filter(Usuario.email == data['email'], Usuario.id_usuario != id_usuario).first():
        return jsonify({"message": "Este e-mail já está em uso por outro usuário."}), 409
    
    if 'nome_usuario' in data: target_user.nome_usuario = data['nome_usuario']
    if 'email' in data: target_user.email = data['email']
    if 'nivel' in data and 'nivel' in allowed_fields_to_edit:
         if current_user_level == 'supervisor' and data['nivel'] == 'admin':
              return jsonify({"message": "Supervisor não pode promover usuário para Administrador."}), 403
         target_user.nivel = data['nivel']
    if 'password' in data: target_user.password = data['password']
        
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"ERRO AO ATUALIZAR USUARIO ID {id_usuario}: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro ao salvar atualizações", "error": str(e)}), 500
        
    return jsonify(UsuarioSchema().dump(target_user))


@usuarios_bp.route('/<int:id_usuario>', methods=['DELETE'])
@jwt_required()
@admin_required() # Somente Admin pode deletar usuários
def deletar_usuario(id_usuario):
    current_user_id_str = get_jwt_identity()
    
    if str(id_usuario) == current_user_id_str:
        return jsonify({"message": "Você não pode deletar sua própria conta."}), 403
        
    usuario = Usuario.query.get_or_404(id_usuario)
    try:
        db.session.delete(usuario)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Não é possível deletar este usuário, pois ele está vinculado a outros registros."}), 409
    except Exception as e:
        db.session.rollback()
        logging.error(f"ERRO AO DELETAR USUARIO ID {id_usuario}: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro ao deletar o usuário", "error": str(e)}), 500
        
    return jsonify({"message": f"Usuário ID {id_usuario} deletado com sucesso."})


@usuarios_bp.route('/<int:id_usuario>/avatar', methods=['POST'])
@jwt_required()
def upload_avatar(id_usuario):
    """Faz upload de avatar. Permissão: Admin (qualquer um) ou usuário para si mesmo."""
    current_user_id_str = get_jwt_identity()
    claims = get_jwt()
    current_user_level = claims.get('nivel')

    if not check_permission(current_user_level, current_user_id_str, id_usuario):
         return jsonify({"message": "Você não tem permissão para alterar este avatar."}), 403
        
    usuario = Usuario.query.get_or_404(id_usuario)
    
    if 'file' not in request.files: return jsonify({"message": "Nenhum arquivo enviado"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"message": "Nenhum arquivo selecionado"}), 400

    if file and allowed_file(file.filename):
        _, ext = os.path.splitext(file.filename)
        filename = secure_filename(f"{usuario.id_usuario}_{uuid.uuid4().hex}{ext}")
        # Subpasta específica para avatares
        avatars_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'avatars')
        filepath = os.path.join(avatars_folder, filename)
        
        try:
            os.makedirs(avatars_folder, exist_ok=True)
            
            if usuario.avatar_filename:
                old_filepath = os.path.join(avatars_folder, usuario.avatar_filename)
                if os.path.exists(old_filepath): os.remove(old_filepath)
                
            file.save(filepath)
            usuario.avatar_filename = filename
            db.session.commit()
            return jsonify(UsuarioSchema().dump(usuario)), 200
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao salvar avatar: {e}\n{traceback.format_exc()}")
            return jsonify({"message": "Erro ao salvar o arquivo", "error": str(e)}), 500
    else:
        return jsonify({"message": "Tipo de arquivo não permitido"}), 400