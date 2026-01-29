# /api/resources/clientes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import distinct
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import Cliente, Usina, ClienteAcessoSolarz
from ..schemas.cliente_schema import ClienteSchema, ClienteDetailSchema, UsinaSchema
from ..decorators import admin_required, tecnico_required
from ..services.solarz_service import registrar_acessos_solarz
from sqlalchemy import func, desc
from datetime import datetime, timedelta, date

clientes_bp = Blueprint('clientes', __name__)

# --- Rotas para Clientes ---

@clientes_bp.route('', methods=['POST'])
@jwt_required()
@admin_required()
def criar_cliente():
    data = ClienteSchema().load(request.get_json())
    
    # Verifica se já existe cliente com mesmo nome (case-insensitive)
    existing = Cliente.query.filter(Cliente.nome.ilike(data['nome'])).first()
    if existing:
        return jsonify({"message": "Cliente já existe! Não é possível cadastrar com o mesmo nome."}), 409

    novo_cliente = Cliente(**data)
    db.session.add(novo_cliente)
    db.session.commit()
    return jsonify(ClienteSchema().dump(novo_cliente)), 201

@clientes_bp.route('/search', methods=['GET'])
@jwt_required()
@tecnico_required()
def search_clientes():
    """Busca clientes por nome para autocomplete."""
    query = request.args.get('q', '').strip()
    
    # Requer pelo menos 2 caracteres
    if len(query) < 2:
        return jsonify([]), 200
    
    # Busca case-insensitive limitada a 10 resultados
    clientes = Cliente.query.filter(
        Cliente.nome.ilike(f'%{query}%')
    ).order_by(Cliente.nome).limit(10).all()
    
    # Retorna apenas dados essenciais
    results = [{
        'id_cliente': c.id_cliente,
        'nome_cliente': c.nome,  # Retorna como nome_cliente para o frontend
        'contato_telefone': c.contato_telefone
    } for c in clientes]
    
    return jsonify(results), 200

@clientes_bp.route('', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_clientes():
    """Lista todos os clientes em um formato paginado padronizado."""
    limit = request.args.get('limit', 200, type=int)
    offset = request.args.get('offset', 0, type=int)
    search = request.args.get('search', '').strip()
    
    clientes_query = Cliente.query
    
    if search:
        clientes_query = clientes_query.filter(Cliente.nome.ilike(f'%{search}%'))
        
    clientes_query = clientes_query.order_by(Cliente.nome)
    
    total = clientes_query.count()
    clientes = clientes_query.limit(limit).offset(offset).all()
    
    return jsonify({
        "results": ClienteSchema(many=True).dump(clientes),
        "total": total,
        "limit": limit,
        "offset": offset
    })

@clientes_bp.route('/<int:id_cliente>', methods=['GET'])
@jwt_required()
@tecnico_required()
def detalhar_cliente(id_cliente):
    cliente = Cliente.query.get_or_404(id_cliente)
    return jsonify(ClienteDetailSchema().dump(cliente))

@clientes_bp.route('/<int:id_cliente>', methods=['PUT'])
@jwt_required()
@admin_required()
def atualizar_cliente(id_cliente):
    cliente = Cliente.query.get_or_404(id_cliente)
    data = ClienteSchema(partial=True).load(request.get_json())
    for key, value in data.items():
        setattr(cliente, key, value)
    db.session.commit()
    return jsonify(ClienteSchema().dump(cliente))

@clientes_bp.route('/<int:id_cliente>', methods=['DELETE'])
@jwt_required()
@admin_required()
def deletar_cliente(id_cliente):
    cliente = Cliente.query.get_or_404(id_cliente)
    db.session.delete(cliente)
    db.session.commit()
    return jsonify({"message": f"Cliente ID {id_cliente} deletado com sucesso."})

# --- Rotas para Usinas (como sub-recurso de Clientes) ---

@clientes_bp.route('/<int:id_cliente>/usinas', methods=['POST'])
@jwt_required()
@admin_required()
def criar_usina_para_cliente(id_cliente):
    cliente = Cliente.query.get_or_404(id_cliente)
    data = UsinaSchema().load(request.get_json())
    nova_usina = Usina(id_cliente=cliente.id_cliente, **data)
    db.session.add(nova_usina)
    db.session.commit()
    return jsonify(UsinaSchema().dump(nova_usina)), 201

@clientes_bp.route('/<int:id_cliente>/usinas', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_usinas_do_cliente(id_cliente):
    """Lista todas as usinas de um cliente específico."""
    cliente = Cliente.query.get_or_404(id_cliente)
    return jsonify(UsinaSchema(many=True).dump(cliente.usinas))

@clientes_bp.route('/usinas/<int:id_usina>', methods=['PUT'])
@jwt_required()
@admin_required()
def atualizar_usina(id_usina):
    """Atualiza os dados de uma usina específica."""
    usina = Usina.query.get_or_404(id_usina)
    json_data = request.get_json()
    try:
        data = UsinaSchema(partial=True).load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400
    
    for key, value in data.items():
        setattr(usina, key, value)
        
    db.session.commit()
    return jsonify(UsinaSchema().dump(usina))

@clientes_bp.route('/usinas/<int:id_usina>', methods=['DELETE'])
@jwt_required()
@admin_required()
def deletar_usina(id_usina):
    """Deleta uma usina específica."""
    usina = Usina.query.get_or_404(id_usina)
    try:
        db.session.delete(usina)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Não é possível deletar esta usina, pois ela está vinculada a um chamado ou orçamento."}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao deletar a usina", "error": str(e)}), 500
        
    return jsonify({"message": f"Usina ID {id_usina} deletada com sucesso."})

# --- Endpoint para listar cidades únicas ---

@clientes_bp.route('/usinas/cidades', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_cidades_usinas():
    """Retorna lista de cidades únicas onde existem usinas cadastradas."""
    cidades = db.session.query(distinct(Usina.cidade))\
        .filter(Usina.cidade.isnot(None))\
        .filter(Usina.cidade != '')\
        .order_by(Usina.cidade)\
        .all()
    
    return jsonify([cidade[0] for cidade in cidades if cidade[0]])

# --- Rotas de Analytics / SolarZ Integration ---

@clientes_bp.route('/dashboard/acessos', methods=['GET'])
@jwt_required()
@tecnico_required()
def dashboard_acessos():
    """
    Retorna KPIs e dados para o dashboard de acessos SolarZ.
    Query Params: de (YYYY-MM-DD), ate (YYYY-MM-DD)
    """
    try:
        # 1. Filtro de Datas (Default: 30 dias)
        ate_str = request.args.get('ate')
        de_str = request.args.get('de')
        
        hoje = datetime.utcnow().date()
        date_ate = datetime.strptime(ate_str, '%Y-%m-%d').date() if ate_str else hoje
        date_de = datetime.strptime(de_str, '%Y-%m-%d').date() if de_str else (hoje - timedelta(days=30))
        
        # 2. Base Query
        base_query = db.session.query(ClienteAcessoSolarz).filter(
            ClienteAcessoSolarz.data_ref >= date_de,
            ClienteAcessoSolarz.data_ref <= date_ate
        )
        
        total_acessos_list = base_query.all()
        
        # 3. KPIs Gerais
        total_clientes_sistema = Cliente.query.count()
        
        # Clientes únicos que tiveram acesso no período
        ativos_ids = {r.cliente_id_solarz for r in total_acessos_list}
        ativos_no_periodo = len(ativos_ids)
        
        total_acessos_estimados = sum(r.qtd_acessos_estimados for r in total_acessos_list)
        
        media_acessos = 0
        if ativos_no_periodo > 0:
            media_acessos = total_acessos_estimados / ativos_no_periodo
            
        # 4. Séries Temporais (Gráficos)
        # Agrupa por dia em memória (ou SQL avançado, mas memória é rápido p/ ranges curtos)
        series_map = {}
        # Inicializa o range com zeros
        delta = date_ate - date_de
        for i in range(delta.days + 1):
            d = date_de + timedelta(days=i)
            series_map[d] = {"acessos": 0, "clientes": 0, "clientes_set": set()}
            
        for r in total_acessos_list:
            if r.data_ref in series_map:
                series_map[r.data_ref]["acessos"] += r.qtd_acessos_estimados
                series_map[r.data_ref]["clientes_set"].add(r.cliente_id_solarz)
                
        # Formata para JSON
        series_acessos = []
        series_clientes = []
        datas_ordenadas = sorted(series_map.keys())
        
        for d in datas_ordenadas:
            data_iso = d.isoformat()
            series_acessos.append({"data": data_iso, "valor": series_map[d]["acessos"]})
            series_clientes.append({"data": data_iso, "valor": len(series_map[d]["clientes_set"])})
            
        # 5. Ranking Geral
        ranking_map = {}
        for r in total_acessos_list:
            cid = r.cliente_id_solarz
            if cid not in ranking_map:
                ranking_map[cid] = {"acessos": 0, "ultimo": r.ultimo_acesso_detectado}
            
            ranking_map[cid]["acessos"] += r.qtd_acessos_estimados
            if r.ultimo_acesso_detectado and (ranking_map[cid]["ultimo"] is None or r.ultimo_acesso_detectado > ranking_map[cid]["ultimo"]):
                ranking_map[cid]["ultimo"] = r.ultimo_acesso_detectado
                
        ranking_list = []
        for cid, data in ranking_map.items():
            ranking_list.append({
                "cliente_id_solarz": cid,
                "acessos": data["acessos"],
                "ultimo_acesso": data["ultimo"]
            })
            
        def enrich_ranking(lista):
            enriched = []
            for item in lista:
                c = Cliente.query.filter_by(solarz_id=item['cliente_id_solarz']).first()
                enriched.append({
                    "cliente_id": c.id_cliente if c else None,
                    "solarz_id": item['cliente_id_solarz'],
                    "nome": c.nome if c else "Desconhecido",
                    "acessos": item['acessos'],
                    "ultimo_acesso": (item['ultimo_acesso'].isoformat() + 'Z') if item['ultimo_acesso'] else None
                })
            return enriched

        ranking_sorted = sorted(ranking_list, key=lambda x: x['acessos'], reverse=True)
        top_10 = ranking_sorted[:10]
        bottom_10 = ranking_sorted[-10:] if len(ranking_sorted) >= 10 else ranking_sorted[::-1]

        # --- VIP ANALYTICS (PREMIUM) ---
        TAG_VIP = "Serviço de monitoramento ativo"
        
        # 1. Identificar Clientes VIP (que tem usina com a tag)
        vips_query = db.session.query(Cliente.solarz_id)\
            .join(Usina)\
            .filter(Usina.tags.ilike(f'%{TAG_VIP}%'))\
            .filter(Cliente.solarz_id.isnot(None))\
            .distinct()
            
        vip_ids_set = {r[0] for r in vips_query.all()}
        total_vips = len(vip_ids_set)
        
        # 2. KPIs VIP
        # Clientes VIP que acessaram no periodo
        vip_ativos_count = len([cid for cid in ativos_ids if cid in vip_ids_set])
        
        # Filtra acessos de VIPs
        vip_acessos_raw = [r for r in total_acessos_list if r.cliente_id_solarz in vip_ids_set]
        vip_total_acessos = sum(r.qtd_acessos_estimados for r in vip_acessos_raw)
        
        # 3. Série Temporal VIP
        series_vip_map = {d: 0 for d in sorted(series_map.keys())}
        for r in vip_acessos_raw:
            if r.data_ref in series_vip_map:
                series_vip_map[r.data_ref] += r.qtd_acessos_estimados
        
        series_vip_chart = [{"data": d.isoformat(), "valor": series_vip_map[d]} for d in sorted(series_vip_map.keys())]
        
        # 4. Ranking VIP
        # Filtra a lista de ranking geral para manter apenas VIPs
        vip_ranking_filtered = [item for item in ranking_list if item['cliente_id_solarz'] in vip_ids_set]
        vip_ranking_sorted = sorted(vip_ranking_filtered, key=lambda x: x['acessos'], reverse=True)
        vip_ranking_enriched = enrich_ranking(vip_ranking_sorted[:50]) # Lista top 50 VIPs

        return jsonify({
            "range": {"de": date_de.isoformat(), "ate": date_ate.isoformat()},
            "kpis": {
                "total_clientes": total_clientes_sistema,
                "ativos_no_periodo": ativos_no_periodo,
                "total_acessos_estimados": total_acessos_estimados,
                "media_acessos_por_cliente_ativo": round(media_acessos, 2)
            },
            "series": {
                "acessos_por_dia": series_acessos,
                "clientes_ativos_por_dia": series_clientes
            },
            "ranking": {
                "top_mais_ativos": enrich_ranking(top_10),
                "top_menos_ativos": enrich_ranking(bottom_10) if len(ranking_list) > 10 else []
            },
            "vip_stats": {
                "total_vips": total_vips,
                "ativos_30d": vip_ativos_count,
                "total_acessos": vip_total_acessos,
                "series_acessos": series_vip_chart,
                "ranking": vip_ranking_enriched
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"message": "Erro ao gerar dashboard", "error": str(e)}), 500

@clientes_bp.route('/solarz/registrar-acessos', methods=['POST'])
@jwt_required()
@admin_required()
def trigger_registrar_acessos():
    """Dispara manualmente o cálculo de histórico de acessos."""
    try:
        stats = registrar_acessos_solarz()
        return jsonify({"ok": True, "stats": stats})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500