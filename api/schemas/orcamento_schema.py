# /api/schemas/orcamento_schema.py (VERSÃO CORRIGIDA)

from marshmallow import Schema, fields, validate, EXCLUDE
from marshmallow.fields import Nested
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models import Orcamento # Importa o modelo base

# --- CORREÇÃO DE IMPORTAÇÃO CIRCULAR ---
# Importa os schemas simples do novo arquivo compartilhado
from .shared_schemas import ClienteSchemaSimples, UsinaSchemaSimples, UsuarioSchemaSimples
# --- FIM DA CORREÇÃO ---

# Schema base para validação de entrada de itens
class ItemOrcamentoBaseSchema(Schema):
    id = fields.Int(required=True)
    quantidade = fields.Int(required=True, validate=validate.Range(min=1))

# --- Schemas de Saída de Itens ---
class MaterialItemSchema(Schema):
    tipo = fields.Constant("material", dump_only=True)
    id = fields.Int(attribute="material.id_material", dump_only=True)
    nome = fields.Str(attribute="material.nome_material", dump_only=True)
    quantidade = fields.Int(dump_only=True)
    valor_unitario = fields.Decimal(attribute="valor_unitario_cobrado", as_string=True, dump_only=True)
    valor_total = fields.Method("get_valor_total", dump_only=True)
    def get_valor_total(self, obj):
        return float(obj.quantidade * obj.valor_unitario_cobrado)

class ServicoItemSchema(Schema):
    tipo = fields.Constant("servico", dump_only=True)
    id = fields.Int(attribute="servico.id_servico", dump_only=True)
    nome = fields.Str(attribute="servico.nome_servico", dump_only=True)
    quantidade = fields.Int(dump_only=True)
    valor_unitario = fields.Decimal(attribute="valor_cobrado", as_string=True, dump_only=True)
    valor_total = fields.Method("get_valor_total", dump_only=True)
    def get_valor_total(self, obj):
        return float(obj.quantidade * obj.valor_cobrado)

# --- Schemas Principais do Orçamento ---
class OrcamentoInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE  # ignora campos extras enviados pelo frontend

    id_cliente = fields.Int(required=True)
    id_usina = fields.Int(required=True)
    descricao_servico = fields.Str(required=True)
    id_chamado = fields.Int(allow_none=True)
    desconto = fields.Decimal(as_string=True, places=2, load_default='0.00')
    data_validade = fields.DateTime(format='iso', allow_none=True)
    materiais = fields.List(Nested(ItemOrcamentoBaseSchema), load_default=[])
    servicos = fields.List(Nested(ItemOrcamentoBaseSchema), load_default=[])
    modalidade = fields.Str(allow_none=True) # Novo campo

class OrcamentoUpdateSchema(OrcamentoInputSchema):
    class Meta:
        unknown = EXCLUDE

    status = fields.Str(validate=validate.OneOf(["pendente", "aprovado", "rejeitado", "cancelado", "arquivado"]))

class OrcamentoOutputSchema(Schema):
    id_orcamento = fields.Int(dump_only=True)
    id_chamado = fields.Int(dump_only=True)
    data_criacao = fields.DateTime(format='iso')
    data_validade = fields.DateTime(format='iso')
    descricao_servico = fields.Str()
    status = fields.Str()
    modalidade = fields.Str() # Novo campo
    cliente = fields.Nested(ClienteSchemaSimples, dump_only=True)
    usina = fields.Nested(UsinaSchemaSimples, dump_only=True)
    usuario_criador = fields.Nested(UsuarioSchemaSimples, attribute="usuario", dump_only=True)
    itens_orcamento = fields.Method("get_itens_formatados", dump_only=True)
    valor_total_itens = fields.Decimal(as_string=True)
    desconto = fields.Decimal(as_string=True)
    valor_deslocamento = fields.Decimal(as_string=True)
    valor_total_final = fields.Decimal(as_string=True)
    mapa_localizacao = fields.Dict(dump_only=True)
    
    def get_itens_formatados(self, obj):
        materiais_formatados = MaterialItemSchema(many=True).dump(obj.materiais)
        servicos_formatados = ServicoItemSchema(many=True).dump(obj.servicos)
        return materiais_formatados + servicos_formatados
