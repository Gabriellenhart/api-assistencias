# /api/schemas/usuario_schema.py

# A correção está nesta linha: EXCLUDE foi adicionado.
from marshmallow import Schema, fields, validate, EXCLUDE

class LoginSchema(Schema):
    """
    Schema para validar os dados de entrada do endpoint de login.
    """
    email = fields.Email(required=True, error_messages={"required": "O e-mail é obrigatório."})
    password = fields.Str(required=True, validate=validate.Length(min=6), error_messages={"required": "A senha é obrigatória."})

class UsuarioSchema(Schema):
    """Schema para serializar os dados de um usuário (sem a senha)."""
    id_usuario = fields.Int(dump_only=True)
    nome_usuario = fields.Str(required=True)
    email = fields.Email(required=True)
    avatar_filename = fields.Str(dump_only=True)
    theme_preference = fields.Str(dump_only=True)
    nivel = fields.Str(required=True, validate=validate.OneOf(
        ["admin", "supervisor", "tecnico"]
    ))

class UsuarioInputSchema(UsuarioSchema):
    """Schema para validar a criação de um usuário (inclui a senha)."""
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=8))
    
    class Meta:
        # Agora esta linha funcionará sem erros
        unknown = EXCLUDE # Ignora campos desconhecidos na entrada