from marshmallow import Schema, fields, validate

class SystemUpdateSchema(Schema):
    """Schema para validação de atualizações do sistema."""
    id = fields.Int(dump_only=True)
    version = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    title = fields.Str(required=True, validate=validate.Length(min=3, max=255))
    description = fields.Str(required=True) # Markdown não tem limite rígido aqui, mas é texto
    created_at = fields.DateTime(dump_only=True, format='iso')
    
    # Informações do autor
    id_usuario = fields.Int(dump_only=True)
    usuario_nome = fields.Str(attribute="usuario.nome_usuario", dump_only=True)
    usuario_avatar = fields.Str(attribute="usuario.avatar_filename", dump_only=True)
