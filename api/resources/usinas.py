# /api/resources/usinas.py (NOVO ARQUIVO)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from .. import db
from ..models import Usina, Cliente
from ..schemas.catalogo_schema import UsinaSchema
from ..decorators import admin_required, tecnico_required, supervisor_or_admin_required

usinas_bp = Blueprint('usinas', __name__)

@usinas_bp.route('', methods=['POST'])
@jwt_required()
@supervisor_or_admin_required() # Permite que admin ou supervisor criem
def criar_usina():
    """Cria uma nova usina (associada a um cliente existente)."""
    json_data = request.get_json()
    schema = UsinaSchema()
    try:
        # Valida os dados e já inclui o id_cliente
        nova_usina = schema.load(json_data, session=db.session)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400

    if not Cliente.query.get(nova_usina.id_cliente):
        return jsonify({"message": "Cliente não encontrado"}), 404

    # Verifica se já existe usina com mesmo id_cliente e uc
    # A constraint ux_usinas_cliente_uc não permite duplicatas
    usina_existente = Usina.query.filter_by(id_cliente=nova_usina.id_cliente, uc=nova_usina.uc).first()
    if usina_existente:
         return jsonify({
             "message": "Já existe uma usina cadastrada para este cliente com esta Unidade Consumidora (UC).",
             "error_code": "DUPLICATE_USINA",
             "existing_id": usina_existente.id_usina
         }), 409

    db.session.add(nova_usina)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "message": "Conflito ao criar usina. Verifique se a UC já não está cadastrada para este cliente.",
            "error_code": "INTEGRITY_ERROR"
        }), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro interno ao salvar usina", "error": str(e)}), 500

    # Recarrega o objeto com o cliente aninhado para o retorno
    result = Usina.query.options(joinedload(Usina.cliente)).get(nova_usina.id_usina)
    return jsonify(schema.dump(result)), 201

@usinas_bp.route('', methods=['GET'])
@jwt_required()
@tecnico_required() # Todos logados podem ver a lista
def listar_usinas():
    """Lista todas as usinas, com os dados do cliente aninhados."""
    # Usa joinedload para otimizar a busca, trazendo os dados do cliente junto
    usinas = Usina.query.options(joinedload(Usina.cliente)).order_by(Usina.nome_usina).all()
    return jsonify(UsinaSchema(many=True).dump(usinas))

@usinas_bp.route('/<int:id_usina>', methods=['GET'])
@jwt_required()
@tecnico_required()
def detalhar_usina(id_usina):
    """Retorna os detalhes de uma usina específica."""
    usina = Usina.query.options(joinedload(Usina.cliente)).get_or_404(id_usina)
    return jsonify(UsinaSchema().dump(usina))

@usinas_bp.route('/<int:id_usina>', methods=['PUT'])
@jwt_required()
@supervisor_or_admin_required() # Apenas admin/supervisor podem editar
def atualizar_usina(id_usina):
    """Atualiza uma usina existente."""
    usina = Usina.query.get_or_404(id_usina)
    json_data = request.get_json()

    schema = UsinaSchema(partial=True)
    try:
        data = schema.load(json_data, instance=usina, session=db.session)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400

    db.session.commit()

    result = Usina.query.options(joinedload(Usina.cliente)).get(usina.id_usina)
    return jsonify(schema.dump(result))

@usinas_bp.route('/<int:id_usina>', methods=['DELETE'])
@jwt_required()
@admin_required() # Apenas Admin pode deletar
def deletar_usina(id_usina):
    """Deleta uma usina."""
    usina = Usina.query.get_or_404(id_usina)
    try:
        db.session.delete(usina)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Não é possível deletar esta usina, pois ela está vinculada a chamados ou orçamentos."}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao deletar a usina", "error": str(e)}), 500

    return jsonify({"message": f"Usina ID {id_usina} deletada com sucesso."})

@usinas_bp.route('/todas-usinas', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_todas_usinas():
    """
    Lista todas as usinas cadastradas e retorna um objeto com resumo de performance e a lista.
    Estrutura: { "resumo": { "total": int, "ok": int, "media": int, "critica": int }, "usinas": [...] }
    """
    import json
    
    usinas = Usina.query.options(joinedload(Usina.cliente)).order_by(Usina.nome_usina).all()
    
    lista_usinas = []
    
    # Contadores para o resumo
    stats = {
        "total": 0,
        "ok": 0,    # >= 90%
        "media": 0, # >= 75% e < 90%
        "critica": 0 # < 75% ou sem dados
    }
    
    for usina in usinas:
        # Serializa dados básicos
        dados_usina = UsinaSchema().dump(usina)
        
        # Performance extraction
        performance_1_day = None
        performance_15_days = None
        performance_30_days = None
        
        if usina.solarz_payload:
            try:
                payload = json.loads(usina.solarz_payload)
                if 'resumo' in payload and 'performance' in payload['resumo']:
                    performance_1_day = payload['resumo']['performance']
                    
                    # Tenta pegar outros periodos se disponiveis (placeholder logic)
                    # No payload atual só vimos 'resumo' genérico, que parece ser diario.
            except Exception:
                pass 
        
        # Injeta dados
        dados_usina['performance_1_day'] = performance_1_day
        dados_usina['performance_15_days'] = performance_15_days
        dados_usina['performance_30_days'] = performance_30_days
        
        lista_usinas.append(dados_usina)
        
        # --- CÁLCULO DO RESUMO ---
        stats["total"] += 1
        
        if performance_1_day is None:
            stats["critica"] += 1
        elif performance_1_day >= 90:
            stats["ok"] += 1
        elif performance_1_day >= 75:
            stats["media"] += 1
        else:
            stats["critica"] += 1

    return jsonify({
        "resumo": stats,
        "usinas": lista_usinas
    })