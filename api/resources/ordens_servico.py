# /api/resources/ordens_servico.py (VERSÃO CORRIGIDA)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from datetime import datetime
from sqlalchemy.orm import joinedload
import logging
import traceback

from .. import db
from ..models import OrdenServico, Usuario # Removido Chamado e Orcamento (não usados aqui)
from ..schemas.ordem_servico_schema import OrdemServicoSchema, OrdemServicoUpdateSchema
from ..services.geolocation_service import calcular_distancia_e_custo

# --- Importações de decorador corrigidas ---
from ..decorators import admin_required, tecnico_required, supervisor_or_admin_required

ordens_servico_bp = Blueprint('ordens_servico', __name__)

# --- A ROTA POST /ordens-servico (criar_ordem_de_servico) FOI REMOVIDA ---
# (A criação agora é feita por POST /orcamentos/<id>/gerar-os)


@ordens_servico_bp.route('', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_ordens_servico():
    """Lista todas as ordens de serviço."""
    
    query = OrdenServico.query.options(
        joinedload(OrdenServico.cliente),
        joinedload(OrdenServico.usina),
        joinedload(OrdenServico.usuario)
    ).filter(
        # Filter: Only Active statuses
        OrdenServico.status.in_(['Aberta', 'Agendado', 'Em Andamento', 'Resolvida', 'Concluida'])
    ).order_by(OrdenServico.data_criacao.desc())
    
    os_list = query.all()
    return jsonify(OrdemServicoSchema(many=True).dump(os_list)), 200

@ordens_servico_bp.route('/<int:id_os>', methods=['GET'])
@jwt_required()
@tecnico_required()
def detalhar_ordem_servico(id_os):
    """Retorna os detalhes de uma Ordem de Serviço específica."""
    os = OrdenServico.query.options(
        joinedload(OrdenServico.itens),
        joinedload(OrdenServico.usina),
        joinedload(OrdenServico.cliente),
        joinedload(OrdenServico.usuario)
    ).get_or_404(id_os)
    
    result = OrdemServicoSchema().dump(os)
    
    # Calcula o deslocamento
    deslocamento_info = calcular_distancia_e_custo(os.usina.latitude, os.usina.longitude)
    
    result['mapa_localizacao'] = {
        "latitude": os.usina.latitude, "longitude": os.usina.longitude,
        "url": f"https://openstreetmap.org/?mlat={os.usina.latitude}&mlon={os.usina.longitude}",
        "distancia_km": deslocamento_info['distancia_km'],
        "tempo_estimado": deslocamento_info['tempo_estimado'],
        "valor_deslocamento": deslocamento_info['valor_deslocamento'],
        "geometry": deslocamento_info.get('geometry')
    }
    return jsonify(result), 200

@ordens_servico_bp.route('/<int:id_os>', methods=['PUT'])
@jwt_required()
@supervisor_or_admin_required() # Decorador corrigido
def atualizar_ordem_servico(id_os):
    """Atualiza o status ou o responsável de uma OS."""
    os = OrdenServico.query.get_or_404(id_os)
    json_data = request.get_json()
    
    schema = OrdemServicoUpdateSchema()
    try:
        data = schema.load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400

    if 'status' in data:
        os.status = data['status']
        if data['status'] == 'Concluida':
            os.data_conclusao = db.func.now()
            
    if 'id_usuario_responsavel' in data:
        Usuario.query.get_or_404(data['id_usuario_responsavel'])
        os.id_usuario_responsavel = data['id_usuario_responsavel']

    try:
        db.session.commit()
        return jsonify(OrdemServicoSchema().dump(os)), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"ERRO AO ATUALIZAR OS: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro interno ao salvar a OS", "error": str(e)}), 500


@ordens_servico_bp.route('/<int:id_os>', methods=['DELETE'])
@jwt_required()
@admin_required() # Decorador corrigido
def deletar_ordem_servico(id_os):
    """Deleta uma Ordem de Serviço."""
    os = OrdenServico.query.get_or_404(id_os)
    
    try:
        db.session.delete(os)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao deletar a Ordem de Serviço", "error": str(e)}), 500
        
    return jsonify({"message": f"Ordem de Serviço ID {id_os} deletada com sucesso."}), 200
