# /api/schemas/chamado_schema.py (VERSÃO CORRIGIDA)

from marshmallow import Schema, fields, validate

# --- CORREÇÃO DE IMPORTAÇÃO ---
# Importa os schemas compartilhados CORRETOS
from .shared_schemas import ClienteSchemaSimples, UsinaSchemaSimples, UsuarioSchemaSimples, ChamadoSchemaSimples
# --- FIM DA CORREÇÃO ---

# Lista de status válidos
# Lista de status válidos removida para validação dinâmica

class ChamadoInputSchema(Schema):
    """Schema para validar a entrada (POST/PUT) de um chamado."""
    id_cliente = fields.Int(required=True)
    id_usina = fields.Int(required=True)
    titulo = fields.Str(required=True, validate=validate.Length(min=5, max=255))
    descricao = fields.Str(required=True)
    categoria = fields.Str(required=True)
    prioridade = fields.Str(required=True, validate=validate.OneOf(["Baixa", "Média", "Alta", "Urgente"]))
    status = fields.Str() # Validação dinâmica no resource
    data_agendamento = fields.DateTime(format='iso', required=False, allow_none=True)
    comentario = fields.Str(required=False, load_only=True)
    id_usuario_responsavel = fields.Int(required=False) 

class ChamadoOutputSchema(Schema):
    """Schema para formatar a saída (GET) de um chamado."""
    id_chamado = fields.Int(dump_only=True)
    is_active = fields.Boolean(dump_only=True)
    titulo = fields.Str()
    descricao = fields.Str()
    categoria = fields.Str()
    prioridade = fields.Str()
    status = fields.Str()
    data_criacao = fields.DateTime(format='iso')
    data_atualizacao = fields.DateTime(format='iso')
    
    cliente = fields.Nested(ClienteSchemaSimples, dump_only=True)
    usina = fields.Nested(UsinaSchemaSimples, dump_only=True)
    
    # Usa o 'UsuarioSchemaSimples' (que contém o avatar)
    usuario_responsavel = fields.Nested(UsuarioSchemaSimples, attribute="usuario", dump_only=True)
    
    orcamentos = fields.Nested('OrcamentoLinkSchema', many=True, dump_only=True)
    lembretes = fields.Nested('ChamadoLembreteSchema', many=True, dump_only=True)

class OrcamentoLinkSchema(Schema):
    id_orcamento = fields.Int()
    status = fields.Str()
    valor_total_final = fields.Float()

class ChamadoAnexoSchema(Schema):
    id = fields.Int(attribute="id_anexo")
    nome = fields.Str(attribute="nome_arquivo")
    url = fields.Method("get_url")
    tipo = fields.Str(attribute="mime_type")
    tamanho = fields.Int(attribute="tamanho_bytes")
    
    def get_url(self, obj):
        # Retorna URL relativa para a API
        return f"/static/{obj.caminho_arquivo}"

class ChamadoLembreteSchema(Schema):
    id_lembrete = fields.Int()
    titulo = fields.Str()
    data_lembrete = fields.DateTime(format='iso')
    status = fields.Str()
    data_criacao = fields.DateTime(format='iso')
    data_conclusao = fields.DateTime(format='iso', allow_none=True)

class ChamadoLogSchema(Schema):
    """Schema para formatar a saída (GET) dos logs."""
    id = fields.Int(dump_only=True)
    id_chamado = fields.Int(dump_only=True)  # ID do chamado relacionado
    timestamp = fields.DateTime(format='iso')
    tipo_log = fields.Str(dump_only=True)
    comentario = fields.Str(dump_only=True, dump_default=None)
    campo_alterado = fields.Str()
    valor_antigo = fields.Str()
    valor_novo = fields.Str()
    
    # Garante que o log também use o schema de usuário correto
    usuario = fields.Nested(UsuarioSchemaSimples, dump_only=True)
    # Inclui detalhes básicos do chamado no log
    chamado = fields.Nested(ChamadoSchemaSimples, dump_only=True)
    anexos = fields.Nested(ChamadoAnexoSchema, many=True, dump_only=True)
    lembretes = fields.Nested(ChamadoLembreteSchema, many=True, dump_only=True)