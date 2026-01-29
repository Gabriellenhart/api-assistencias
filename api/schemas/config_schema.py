# /api/schemas/config_schema.py (NOVO ARQUIVO)

from marshmallow import Schema, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models import Categoria, Parametro, Modalidade

class CategoriaSchema(SQLAlchemyAutoSchema):
    """
    Schema para serializar e validar os dados da Categoria.
    Usa SQLAlchemyAutoSchema para criar campos automaticamente.
    """
    class Meta:
        model = Categoria
        load_instance = True # Permite carregar dados de volta para um objeto Categoria
        include_fk = True
    
    # Garante que 'nome' seja obrigatório na criação/atualização
    nome = fields.Str(required=True, validate=validate.Length(min=2))

class ParametroSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Parametro
        load_instance = True

class ModalidadeSchema(SQLAlchemyAutoSchema):
    configuracao = fields.Raw(allow_none=True) # Permite JSON/Dict

    class Meta:
        model = Modalidade
        load_instance = True