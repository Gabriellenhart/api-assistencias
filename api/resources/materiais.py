# /api/resources/materiais.py (VERSÃO FINAL E COMPLETA)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import Material
from ..schemas.catalogo_schema import MaterialSchema
from ..decorators import admin_required, tecnico_required

materiais_bp = Blueprint('materiais', __name__)

@materiais_bp.route('', methods=['POST'])
@jwt_required()
@admin_required()
def criar_material():
    json_data = request.get_json()
    try:
        data = MaterialSchema().load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400
        
    novo_material = Material(**data)
    db.session.add(novo_material)
    db.session.commit()
    return jsonify(MaterialSchema().dump(novo_material)), 201

@materiais_bp.route('', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_materiais():
    materiais = Material.query.order_by(Material.nome_material).all()
    return jsonify(MaterialSchema(many=True).dump(materiais))

# --- ROTAS FALTANTES ADICIONADAS AQUI ---

@materiais_bp.route('/<int:id_material>', methods=['GET'])
@jwt_required()
@tecnico_required()
def detalhar_material(id_material):
    """Retorna os detalhes de um material específico."""
    material = Material.query.get_or_404(id_material)
    return jsonify(MaterialSchema().dump(material))

@materiais_bp.route('/<int:id_material>', methods=['PUT'])
@jwt_required()
@admin_required()
def atualizar_material(id_material):
    """Atualiza um material existente."""
    material = Material.query.get_or_404(id_material)
    json_data = request.get_json()
    try:
        data = MaterialSchema(partial=True).load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400
    
    for key, value in data.items():
        setattr(material, key, value)
        
    db.session.commit()
    return jsonify(MaterialSchema().dump(material))

@materiais_bp.route('/<int:id_material>', methods=['DELETE'])
@jwt_required()
@admin_required()
def deletar_material(id_material):
    """Deleta um material."""
    material = Material.query.get_or_404(id_material)
    try:
        db.session.delete(material)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Não é possível deletar este material, pois ele está vinculado a um ou mais orçamentos."}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao deletar o material", "error": str(e)}), 500
        
    return jsonify({"message": f"Material ID {id_material} deletado com sucesso."})