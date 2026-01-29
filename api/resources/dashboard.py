# /api/resources/dashboard.py (VERSÃO CORRIGIDA COM ID_CHAMADO)

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, distinct, extract
from datetime import datetime, timedelta

from .. import db
from ..models import Chamado, Orcamento, OrdenServico, Cliente, ChamadoLog
from ..schemas.dashboard_schema import DashboardStatsSchema
from ..decorators import tecnico_required

dashboard_bp = Blueprint('dashboard', __name__)

# --- FUNÇÃO AUXILIAR PARA O GRÁFICO DE LINHA ---
def get_picos_atividade():
    """Busca o volume de atividades (Chamados, Orçamentos, OS) dos últimos 6 meses."""
    labels = []
    chamados_data = {}
    orcamentos_data = {}
    os_data = {}
    
    hoje = datetime.utcnow().date()
    nomes_meses_pt = [
        "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez"
    ]
    
    for i in range(5, -1, -1):
        mes = (hoje.month - i - 1) % 12
        ano = hoje.year + (hoje.month - i - 1) // 12
        label_key = f"{ano}-{mes + 1:02d}"
        label_display = nomes_meses_pt[mes]
        
        labels.append(label_display)
        chamados_data[label_key] = 0
        orcamentos_data[label_key] = 0
        os_data[label_key] = 0

    seis_meses_atras = hoje.replace(day=1) - timedelta(days=150)
    date_format_string = 'YYYY-MM'
    
    query_chamados = db.session.query(
        func.to_char(Chamado.data_criacao, date_format_string).label('mes'),
        func.count(Chamado.id_chamado).label('total')
    ).filter(Chamado.data_criacao >= seis_meses_atras).group_by('mes').all()
    
    for row in query_chamados:
        if row.mes in chamados_data:
            chamados_data[row.mes] = row.total

    query_orcamentos = db.session.query(
        func.to_char(Orcamento.data_criacao, date_format_string).label('mes'),
        func.count(Orcamento.id_orcamento).label('total')
    ).filter(Orcamento.data_criacao >= seis_meses_atras).group_by('mes').all()

    for row in query_orcamentos:
        if row.mes in orcamentos_data:
            orcamentos_data[row.mes] = row.total
            
    query_os = db.session.query(
        func.to_char(OrdenServico.data_criacao, date_format_string).label('mes'),
        func.count(OrdenServico.id_orden_servico).label('total')
    ).filter(OrdenServico.data_criacao >= seis_meses_atras).group_by('mes').all()

    for row in query_os:
        if row.mes in os_data:
            os_data[row.mes] = row.total

    return {
        "labels": labels,
        "chamados": list(chamados_data.values()),
        "orcamentos": list(orcamentos_data.values()),
        "ordens_servico": list(os_data.values())
    }

# --- FUNÇÃO AUXILIAR PARA MÉTRICAS ---
def get_metricas_qualidade(periodo_atual_inicio, periodo_anterior_inicio):
    """Calcula as métricas de qualidade para o período atual vs. anterior."""
    
    status_resolvidos_metricas = ['Resolvido', 'OS Resolvida']
    
    # 1. Tempo Médio de Resolução (TMR)
    query_tmr_atual = db.session.query(
        func.avg(extract('epoch', Chamado.data_atualizacao) - extract('epoch', Chamado.data_criacao))
    ).filter(
        Chamado.status.in_(status_resolvidos_metricas),
        func.date(Chamado.data_atualizacao) >= periodo_atual_inicio
    ).scalar()
    tmr_atual_dias = (query_tmr_atual / 86400) if query_tmr_atual else 0

    query_tmr_anterior = db.session.query(
        func.avg(extract('epoch', Chamado.data_atualizacao) - extract('epoch', Chamado.data_criacao))
    ).filter(
        Chamado.status.in_(status_resolvidos_metricas),
        func.date(Chamado.data_atualizacao) >= periodo_anterior_inicio,
        func.date(Chamado.data_atualizacao) < periodo_atual_inicio
    ).scalar()
    tmr_anterior_dias = (query_tmr_anterior / 86400) if query_tmr_anterior else 0

    # 2. Taxa de Aprovação de Orçamentos (TAO)
    def calcular_tao(inicio, fim=None):
        query = Orcamento.query.filter(
            func.date(Orcamento.data_criacao) >= inicio
        )
        if fim:
            query = query.filter(func.date(Orcamento.data_criacao) < fim)
            
        total = query.count()
        aprovados = query.filter(Orcamento.status == 'aprovado').count()
        return (aprovados / total) * 100 if total > 0 else 0

    tao_atual = calcular_tao(periodo_atual_inicio)
    tao_anterior = calcular_tao(periodo_anterior_inicio, periodo_atual_inicio)

    return {
        "tempo_medio_resolucao": {
            "atual": tmr_atual_dias,
            "anterior": tmr_anterior_dias
        },
        "taxa_aprovacao_orcamento": {
            "atual": tao_atual,
            "anterior": tao_anterior
        }
    }

# --- ENDPOINT PRINCIPAL ---
@dashboard_bp.route('', methods=['GET'])
@jwt_required()
@tecnico_required()
def get_dashboard_stats():
    """
    Consolida e retorna todas as estatísticas para a dashboard principal.
    """
    
    hoje = datetime.utcnow().date()
    trinta_dias_atras = hoje - timedelta(days=30)
    periodo_atual_inicio = hoje - timedelta(days=30)
    periodo_anterior_inicio = hoje - timedelta(days=60)

    # --- 1. Cálculos dos KPIs (Últimos 30 dias) ---
    
    status_chamado_aberto = [
        "Aberto", "Resolvendo", "Aguardando Cliente", "Aguardando Assistênca", 
        "Aguardando NF", "Aguardando Garantia", "Aguardando Pagamento", 
        "OS Aberta", "Executando OS"
    ]
    status_chamado_resolvido = [
        "OS Resolvida", "Resolvido", "Cancelado", "Arquivado"
    ]
    
    chamados_abertos = db.session.query(func.count(Chamado.id_chamado)).filter(
        Chamado.status.in_(status_chamado_aberto),
        func.date(Chamado.data_criacao) >= trinta_dias_atras
    ).scalar()
    
    chamados_resolvidos = db.session.query(func.count(Chamado.id_chamado)).filter(
        Chamado.status.in_(status_chamado_resolvido),
        func.date(Chamado.data_atualizacao) >= trinta_dias_atras
    ).scalar()

    orcamentos_abertos = db.session.query(func.count(Orcamento.id_orcamento)).filter(
        Orcamento.status == 'pendente',
        func.date(Orcamento.data_criacao) >= trinta_dias_atras
    ).scalar()
    
    orcamentos_aprovados = db.session.query(func.count(Orcamento.id_orcamento)).filter(
        Orcamento.status == 'aprovado',
        func.date(Orcamento.data_criacao) >= trinta_dias_atras
    ).scalar()

    status_os_aberta = ['Aberta', 'Em Andamento']
    status_os_concluida = ['Concluida', 'Cancelada']
    
    os_abertas = db.session.query(func.count(OrdenServico.id_orden_servico)).filter(
        OrdenServico.status.in_(status_os_aberta), 
        func.date(OrdenServico.data_criacao) >= trinta_dias_atras
    ).scalar()
    
    os_concluidas = db.session.query(func.count(OrdenServico.id_orden_servico)).filter(
        OrdenServico.status.in_(status_os_concluida), 
        func.date(OrdenServico.data_criacao) >= trinta_dias_atras
    ).scalar()

    clientes_atendidos = db.session.query(func.count(distinct(Chamado.id_cliente))).filter(
        Chamado.status.in_(['Resolvido', 'OS Resolvida']),
        func.date(Chamado.data_atualizacao) >= trinta_dias_atras
    ).scalar()
    
    clientes_aguardando = db.session.query(func.count(distinct(Chamado.id_cliente))).filter(
        Chamado.status.in_(status_chamado_aberto),
        func.date(Chamado.data_criacao) >= trinta_dias_atras
    ).scalar()

    # --- 2. CÁLCULO DOS TOTAIS HISTÓRICOS ---
    total_chamados = db.session.query(func.count(Chamado.id_chamado)).scalar()
    total_orcamentos = db.session.query(func.count(Orcamento.id_orcamento)).scalar()
    total_os = db.session.query(func.count(OrdenServico.id_orden_servico)).scalar()
    total_clientes = db.session.query(func.count(Cliente.id_cliente)).scalar()

    # --- 3. CONSULTA DO FEED (com debug) ---
    ultimas_atividades = ChamadoLog.query.order_by(
        ChamadoLog.timestamp.desc()
    ).limit(10).all()
    
    # DEBUG: Verificar se id_chamado está presente
    print("=== DEBUG FEED ATIVIDADES ===")
    for log in ultimas_atividades:
        print(f"Log ID: {log.id}, Chamado ID: {log.id_chamado}, Campo: {log.campo_alterado}")
    print("=== FIM DEBUG ===")
    
    # --- 4. Montagem do Objeto de Resposta ---
    stats_data = {
        "kpis": {
            "chamados": {
                "abertos": chamados_abertos, 
                "resolvidos": chamados_resolvidos, 
                "total": total_chamados
            },
            "orcamentos": {
                "abertos": orcamentos_abertos, 
                "resolvidos": orcamentos_aprovados, 
                "total": total_orcamentos
            },
            "ordens_servico": {
                "abertos": os_abertas, 
                "resolvidos": os_concluidas, 
                "total": total_os
            },
            "clientes": {
                "atendidos": clientes_atendidos, 
                "aguardando": clientes_aguardando, 
                "total": total_clientes
            }
        },
        "grafico_linha": get_picos_atividade(),
        "grafico_barras": {
            "labels": ["Chamados Abertos", "Orçamentos Aprovados", "OS Concluídas"],
            "data": [chamados_abertos, orcamentos_aprovados, os_concluidas]
        },
        "feed_atividades": ultimas_atividades,
        "metricas_qualidade": get_metricas_qualidade(periodo_atual_inicio, periodo_anterior_inicio)
    }

    return jsonify(DashboardStatsSchema().dump(stats_data)), 200