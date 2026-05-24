# api/resources/briefing.py

from flask import Blueprint, request, jsonify
from api.services.briefing_service import BriefingService
from api.schemas.briefing_schema import DailyBriefing
import os # Para usar a data de referência

briefing_bp = Blueprint('briefing', __name__, url_prefix='/briefing')

# Injeção de dependência (Assumindo que você tem um mecanismo para injetar serviços)
# Em um projeto real, isso seria feito via Blueprints ou um setup de DI.
# Aqui é uma simplificação conceitual.
def create_briefing_route(service: BriefingService):
    
    @briefing_bp.route('/diario', methods=['GET'])
    def get_daily_briefing():
        # 1. Determinar a data de referência (MVP: Hoje)
        date_ref = datetime.now().strftime('%Y-%m-%d')
        
        # 2. Obter o corpo da requisição (se houver filtros além do escopo)
        escopo = request.args.get('escopo', 'chamados')
        
        # 3. Executar o serviço
        try:
            briefing_data = service.generate_daily_briefing(date_ref)
            return jsonify(briefing_data.__dict__), 200
        except Exception as e:
            # Logar o erro em produção
            return jsonify({"error": f"Erro ao gerar briefing: {str(e)}"}), 500

# Onde você registraria esta rota no seu arquivo principal de rotas (ex: api/routes.py)
# routes.register_blueprint(briefing_bp)

api_bp = Blueprint('api', __name__, url_prefix='/api/v1/briefing')

@api_bp.route('/operacional', methods=['GET'])
def get_operacional_briefing_endpoint():
    """
    Endpoint to retrieve the operational briefing summary.
    Supports optional limit query parameter.
    """
    try:
        limit = request.args.get('limit', '20', type=int)
        if limit <= 0:
            limit = 20
    except ValueError:
        limit = 20
        
    try:
        briefing_data = get_operacional_briefing(limit=limit)
        
        # Success response
        return jsonify({
            "success": True,
            "count": len(briefing_data),
            "data": briefing_data,
            "mensaje": "Briefing operacional cargado exitosamente."
        }), 200
        
    except Exception as e:
        # Error response
        return jsonify({
            "success": False,
            "error": "Error al procesar el briefing operacional.",
            "detalle": str(e)
        }), 500