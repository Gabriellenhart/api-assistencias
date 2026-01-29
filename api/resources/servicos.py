# /api/resources/servicos.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import Servico
from ..schemas.catalogo_schema import ServicoSchema
from ..decorators import admin_required, tecnico_required

servicos_bp = Blueprint('servicos', __name__)

@servicos_bp.route('', methods=['POST'])
@jwt_required()
@admin_required()
def criar_servico():
    """Cria um novo serviço no catálogo (Admin only)."""
    json_data = request.get_json()
    schema = ServicoSchema()
    
    try:
        data = schema.load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400

    novo_servico = Servico(**data)
    
    try:
        db.session.add(novo_servico)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao salvar o serviço", "error": str(e)}), 500
    
    return jsonify(schema.dump(novo_servico)), 201


@servicos_bp.route('', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_servicos():
    """Lista todos os serviços do catálogo (Técnicos e Admins)."""
    servicos = Servico.query.order_by(Servico.nome_servico).all()
    schema = ServicoSchema(many=True)
    return jsonify(schema.dump(servicos))


@servicos_bp.route('/<int:id_servico>', methods=['GET'])
@jwt_required()
@tecnico_required()
def detalhar_servico(id_servico):
    """Retorna os detalhes de um serviço específico (Técnicos e Admins)."""
    servico = Servico.query.get_or_404(id_servico)
    schema = ServicoSchema()
    return jsonify(schema.dump(servico))


@servicos_bp.route('/<int:id_servico>', methods=['PUT'])
@jwt_required()
@admin_required()
def atualizar_servico(id_servico):
    """Atualiza um serviço existente (Admin only)."""
    servico = Servico.query.get_or_404(id_servico)
    json_data = request.get_json()
    
    # partial=True permite que apenas alguns campos sejam enviados para atualização
    schema = ServicoSchema(partial=True)
    try:
        data = schema.load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400

    # Atualiza os atributos do objeto com os novos dados
    for key, value in data.items():
        setattr(servico, key, value)
        
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao atualizar o serviço", "error": str(e)}), 500
        
    return jsonify(schema.dump(servico))


@servicos_bp.route('/<int:id_servico>', methods=['DELETE'])
@jwt_required()
@admin_required()
def deletar_servico(id_servico):
    """Deleta um serviço do catálogo (Admin only)."""
    servico = Servico.query.get_or_404(id_servico)
    
    try:
        db.session.delete(servico)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "message": "Erro de integridade: Não é possível deletar este serviço pois ele já está vinculado a um ou mais orçamentos."
        }), 409 # 409 Conflict é um bom status para este caso
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao deletar o serviço", "error": str(e)}), 500
        
    return jsonify({"message": f"Serviço ID {id_servico} deletado com sucesso."})