from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

# Ajuste os imports conforme a estrutura real do projeto
from ..services.solarz_service import processar_sincronizacao_solarz
from ..decorators import admin_required

integracoes_bp = Blueprint('integracoes', __name__)

@integracoes_bp.route('/solarz/sincronizar-usinas', methods=['POST'])
@jwt_required()
@admin_required()
def sincronizar_usinas_solarz():
    """
    Recebe uma lista de objetos 'raw' da SolarZ e processa a sincronização.
    Endpoint idempotente.
    """
    # Verifica o payload
    raw_data = request.get_json()
    
    if not isinstance(raw_data, list):
         # Tenta verificar se veio dentro de um envelope 'content' (comum em APIs paginadas)
         if isinstance(raw_data, dict) and 'content' in raw_data and isinstance(raw_data['content'], list):
             raw_data = raw_data['content']
         else:
             return jsonify({"message": "O corpo da requisição deve ser uma lista de usinas ou objeto com chave 'content'."}), 400
         
    try:
        stats = processar_sincronizacao_solarz(raw_data)
        return jsonify(stats), 200
    except Exception as e:
        # Log detalhado já feito no service
        return jsonify({"message": "Erro processando sincronização", "error": str(e)}), 500
