# /api/schemas/catalogo_schema.py
from marshmallow import Schema, fields
from .orcamento_schema import ClienteSchemaSimples
from marshmallow import Schema, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models import Material, Usina # Adiciona Usina

class MaterialSchema(Schema):
    id_material = fields.Int(dump_only=True)
    nome_material = fields.Str(required=True)
    unidades = fields.Str()
    valor_custo = fields.Decimal(as_string=True, places=2)
    valor_venda = fields.Decimal(as_string=True, places=2)

class ServicoSchema(Schema):
    id_servico = fields.Int(dump_only=True)
    nome_servico = fields.Str(required=True)
    categoria_servico = fields.Str(required=True)
    valor_servico = fields.Decimal(as_string=True, required=True, places=2)

class InversorSchema(Schema):
    id_inversor = fields.Int(dump_only=True)
    marca = fields.Str(required=True)
    modelo = fields.Str()
    potencia = fields.Decimal(as_string=True, places=2)
    # CORREÇÃO APLICADA AQUI: 'default' substituído por 'load_default'
    disponivel = fields.Bool(load_default=True)
    valor_aluguel = fields.Decimal(as_string=True, places=2)

class UsinaSchema(SQLAlchemyAutoSchema):
    """
    Schema completo para Usinas, usado para validação e serialização.
    """
    class Meta:
        model = Usina
        load_instance = True
        include_fk = True # Inclui id_cliente na validação
        exclude = ('solarz_payload', 'solarz_payload_updated_at') # Nunca expor o payload bruto

    # Campos sobrescritos para permitir nulos (SolarZ nem sempre envia)
    latitude = fields.Str(allow_none=True)
    longitude = fields.Str(allow_none=True)
    logradouro = fields.Str(allow_none=True)
    bairro = fields.Str(allow_none=True)
    estado = fields.Str(allow_none=True)
    pais = fields.Str(allow_none=True)
    cep = fields.Str(allow_none=True)
    
    # Novos Campos de Enriquecimento
    uc = fields.Str(allow_none=True)
    dados_planilha = fields.Dict() # Agora editável conforme solicitação
    
    # Campo para serializar o JSON se o banco retornar objeto textual ou dict
    # Para o front, talvez não precisemos expor as chaves solarz_id e uuid na listagem comum,
    # mas admin pode querer ver. Deixaremos o padrão do auto schema.
    
    cliente = fields.Nested(ClienteSchemaSimples, dump_only=True)