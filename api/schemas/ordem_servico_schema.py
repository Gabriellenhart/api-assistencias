# /api/schemas/ordem_servico_schema.py (NOVO ARQUIVO)

from marshmallow import Schema, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models import OrdenServico, OrdemServicoItem

# Importa os schemas simples que já criamos
from .shared_schemas import (
    ClienteSchemaSimples, 
    UsinaSchemaSimples, 
    UsuarioSchemaSimples
)

class OrdemServicoItemSchema(SQLAlchemyAutoSchema):
    """Schema para os itens (checklist) de uma Ordem de Serviço."""
    class Meta:
        model = OrdemServicoItem
        include_fk = True
        load_instance = True

class OrdemServicoSchema(SQLAlchemyAutoSchema):
    """Schema principal para a Ordem de Serviço (Saída/GET)."""
    class Meta:
        model = OrdenServico
        include_relationships = True # Inclui relacionamentos
        load_instance = True

    # Aninha os dados dos relacionamentos para exibição
    cliente = fields.Nested(ClienteSchemaSimples, dump_only=True)
    usina = fields.Nested(UsinaSchemaSimples, dump_only=True)
    usuario = fields.Nested(UsuarioSchemaSimples, attribute="usuario", dump_only=True, data_key="usuario_responsavel")
    
    # Aninha os itens do checklist
    itens = fields.Nested(OrdemServicoItemSchema, many=True, dump_only=True)
    mapa_localizacao = fields.Dict(dump_only=True)
    
class OrdemServicoUpdateSchema(Schema):
    """Schema para ATUALIZAR uma OS (PUT)."""
    
    # Lista de status válidos para uma OS
    VALID_STATUSES = ["Aberta", "Agendado", "Em Andamento", "Concluida", "Cancelada"]
    
    status = fields.Str(validate=validate.OneOf(VALID_STATUSES))
    id_usuario_responsavel = fields.Int(required=False)
    
    # Futuramente, podemos adicionar a atualização de itens concluídos aqui
    # itens_concluidos = fields.List(fields.Int(), required=False)
