from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from datetime import datetime

from .. import db
from ..models import SystemUpdate
from ..schemas.system_update_schema import SystemUpdateSchema
from ..decorators import admin_required

updates_bp = Blueprint('updates', __name__)

@updates_bp.route('', methods=['GET'])
@jwt_required()
def listar_updates():
    """Lista todas as atualizações do sistema, ordenadas por data descrescente e depois versão."""
    updates = SystemUpdate.query.order_by(SystemUpdate.created_at.desc(), SystemUpdate.id.desc()).all()
    schema = SystemUpdateSchema(many=True)
    return jsonify(schema.dump(updates)), 200

@updates_bp.route('', methods=['POST'])
@jwt_required()
@admin_required()
def criar_update():
    """Cria uma nova atualização (Apenas Admin)."""
    current_user_id = get_jwt_identity()
    json_data = request.get_json()
    
    schema = SystemUpdateSchema()
    try:
        data = schema.load(json_data)
    except ValidationError as err:
        return jsonify(err.messages), 400
        
    update = SystemUpdate(
        version=data['version'],
        title=data['title'],
        description=data['description'],
        id_usuario=current_user_id
    )
    
    db.session.add(update)
    db.session.commit()
    
    return jsonify(schema.dump(update)), 201

@updates_bp.route('/<int:id>', methods=['PUT'])
@jwt_required()
@admin_required()
def atualizar_update(id):
    """Edita uma atualização existente."""
    update = SystemUpdate.query.get_or_404(id)
    json_data = request.get_json()
    
    schema = SystemUpdateSchema(partial=True)
    try:
        data = schema.load(json_data)
    except ValidationError as err:
        return jsonify(err.messages), 400
    
    if 'version' in data:
        update.version = data['version']
    if 'title' in data:
        update.title = data['title']
    if 'description' in data:
        update.description = data['description']
        
    db.session.commit()
    return jsonify(SystemUpdateSchema().dump(update)), 200

@updates_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
@admin_required()
def deletar_update(id):
    """Remove uma atualização."""
    update = SystemUpdate.query.get_or_404(id)
    db.session.delete(update)
    db.session.commit()
    return jsonify({"message": "Atualização removida com sucesso"}), 200
