# /api/schemas/shared_schemas.py (NOVO ARQUIVO)

from marshmallow import Schema, fields

"""
Este arquivo contém schemas simples e compartilhados 
para evitar importações circulares.
"""

class ClienteSchemaSimples(Schema):
    """Schema simples para exibir dados aninhados do cliente."""
    id_cliente = fields.Int(dump_only=True)
    nome = fields.Str(dump_only=True)
    cidade = fields.Str(dump_only=True, dump_default=None)

class UsinaSchemaSimples(Schema):
    """Schema simples para exibir dados aninhados da usina."""
    id_usina = fields.Int(dump_only=True)
    nome_usina = fields.Str(dump_only=True)
    cidade = fields.Str(dump_only=True, dump_default=None)

class UsuarioSchemaSimples(Schema):
    """Schema simples para exibir dados do usuário (avatar e nome)."""
    id_usuario = fields.Int(dump_only=True)
    nome_usuario = fields.Str(dump_only=True)
    avatar_filename = fields.Str(dump_only=True)

class ChamadoSchemaSimples(Schema):
    """Schema simples do Chamado para usar em logs."""
    id_chamado = fields.Int(dump_only=True)
    titulo = fields.Str(dump_only=True)
    usina = fields.Nested(UsinaSchemaSimples, dump_only=True)
    cliente = fields.Nested(ClienteSchemaSimples, dump_only=True)