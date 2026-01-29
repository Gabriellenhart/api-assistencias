# /api/schemas/cliente_schema.py
from marshmallow import Schema, fields

class UsinaSchema(Schema):
    id_usina = fields.Int(dump_only=True)
    nome_usina = fields.Str(required=True)
    cidade = fields.Str()
    latitude = fields.Str(required=True)
    longitude = fields.Str(required=True)
    uc = fields.Str()
    dados_planilha = fields.Dict()

class ClienteSchema(Schema):
    id_cliente = fields.Int(dump_only=True)
    nome = fields.Str(required=True)
    contato_telefone = fields.Str()
    dados_planilha = fields.Dict()
    ultimo_acesso = fields.Function(lambda o: f"{o.ultimo_acesso.isoformat()}Z" if o.ultimo_acesso else None)

class ClienteDetailSchema(ClienteSchema):
    usinas = fields.List(fields.Nested(UsinaSchema), dump_only=True)