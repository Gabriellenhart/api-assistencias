# /api/schemas/dashboard_schema.py (VERSÃO CORRIGIDA)

# --- CORREÇÃO APLICADA AQUI ---
# 'Nested' não é importado do 'marshmallow', 
# ele é acessado através de 'fields.Nested'
from marshmallow import Schema, fields 
# --- FIM DA CORREÇÃO ---

from .chamado_schema import ChamadoLogSchema 

# --- Schemas de KPI (sem alteração) ---
class KpiDataSchema(Schema):
    abertos = fields.Int(dump_only=True)
    resolvidos = fields.Int(dump_only=True)
    total = fields.Int(dump_only=True)

class KpiClienteSchema(Schema):
    atendidos = fields.Int(dump_only=True)
    aguardando = fields.Int(dump_only=True)
    total = fields.Int(dump_only=True)

class DashboardKpiSchema(Schema):
    chamados = fields.Nested(KpiDataSchema, dump_only=True)
    orcamentos = fields.Nested(KpiDataSchema, dump_only=True)
    ordens_servico = fields.Nested(KpiDataSchema, dump_only=True)
    clientes = fields.Nested(KpiClienteSchema, dump_only=True)

# --- Schemas de Gráficos (sem alteração) ---
class GraficoLinhaSchema(Schema):
    labels = fields.List(fields.Str(), dump_only=True)
    chamados = fields.List(fields.Int(), dump_only=True)
    orcamentos = fields.List(fields.Int(), dump_only=True)
    ordens_servico = fields.List(fields.Int(), dump_only=True)

class GraficoBarrasSchema(Schema):
    labels = fields.List(fields.Str(), dump_only=True)
    data = fields.List(fields.Int(), dump_only=True)

class MetricaValorSchema(Schema):
    """Armazena o valor atual e o anterior de uma métrica."""
    atual = fields.Float(dump_only=True)
    anterior = fields.Float(dump_only=True)

class DashboardMetricasSchema(Schema):
    """Agrupa todas as métricas de qualidade."""
    tempo_medio_resolucao = fields.Nested(MetricaValorSchema, dump_only=True)
    taxa_aprovacao_orcamento = fields.Nested(MetricaValorSchema, dump_only=True)

# --- Schema Principal (sem alteração) ---
class DashboardStatsSchema(Schema):
    kpis = fields.Nested(DashboardKpiSchema, dump_only=True)
    grafico_linha = fields.Nested(GraficoLinhaSchema, dump_only=True)
    grafico_barras = fields.Nested(GraficoBarrasSchema, dump_only=True)
    feed_atividades = fields.Nested(ChamadoLogSchema, many=True, dump_only=True)
    metricas_qualidade = fields.Nested(DashboardMetricasSchema, dump_only=True)