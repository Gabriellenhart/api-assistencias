# /api/resources/logs.py (VERSÃO ATUALIZADA)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from .. import db
from ..models import ChamadoLog
from ..schemas.chamado_schema import ChamadoLogSchema
from ..decorators import admin_required, supervisor_or_admin_required, tecnico_required

logs_bp = Blueprint('logs', __name__)

@logs_bp.route('', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_logs_globais():
    """
    Lista logs de todo o sistema para o feed global (timeline), com paginação.
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)

        # Busca logs ordenados por data decrescente
        logs_query = ChamadoLog.query.order_by(ChamadoLog.timestamp.desc())
        
        # Paginação
        total = logs_query.count()
        logs = logs_query.limit(limit).offset(offset).all()

        return jsonify({
            "results": ChamadoLogSchema(many=True).dump(logs),
            "total": total,
            "has_more": (offset + limit) < total
        }), 200
        
    except Exception as e:
        return jsonify({"message": "Erro ao listar logs", "error": str(e)}), 500


@logs_bp.route('/<int:log_id>', methods=['PUT'])
@jwt_required()
@tecnico_required()
def atualizar_comentario(log_id):
    """Atualiza um comentário (log manual)."""
    current_user_id = int(get_jwt_identity())
    log = ChamadoLog.query.get_or_404(log_id)

    # Regra: Só pode editar se for 'manual' E (se for o dono OU for admin)
    if log.tipo_log != 'manual':
        return jsonify({"message": "Não é possível editar um log automático."}), 403

    claims = get_jwt()
    if log.id_usuario != current_user_id and claims.get('nivel') != 'admin':
        return jsonify({"message": "Você não tem permissão para editar este comentário."}), 403

    json_data = request.get_json()
    novo_texto = json_data.get('comentario')
    if not novo_texto:
        return jsonify({"message": "O comentário não pode ser vazio."}), 400

    log.comentario = novo_texto
    log.campo_alterado = "Comentário Editado" # Opcional: logar a edição
    db.session.commit()

    return jsonify(ChamadoLogSchema().dump(log)), 200


@logs_bp.route('/<int:log_id>', methods=['DELETE'])
@jwt_required()
@tecnico_required()
def deletar_comentario(log_id):
    """Deleta um comentário (log manual)."""
    current_user_id = int(get_jwt_identity())
    log = ChamadoLog.query.get_or_404(log_id)

    if log.tipo_log != 'manual':
        return jsonify({"message": "Não é possível deletar um log automático."}), 403

    claims = get_jwt()
    if log.id_usuario != current_user_id and claims.get('nivel') != 'admin':
        return jsonify({"message": "Você não tem permissão para deletar este comentário."}), 403

    db.session.delete(log)
    db.session.commit()
    return jsonify({"message": "Comentário deletado com sucesso."}), 200