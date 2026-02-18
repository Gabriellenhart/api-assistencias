# /api/models/__init__.py

from .base import db

# Modelos
from .usuario import Usuario
from .cliente import Cliente, Usina
from .catalogo import Material, Servico, Categoria, Parametro, Modalidade
from .chamado import Chamado
from .chamado_log import ChamadoLog
from .chamado_anexo import ChamadoAnexo
from .orcamento import Orcamento, OrcamentoMaterial, OrcamentoServico
from .ordem_servico import OrdenServico, OrdemServicoItem

from .system_update import SystemUpdate
from .cliente_acesso import ClienteAcessoSolarz
from .chamado_lembrete import ChamadoLembrete
from .configuracao_operacional import ConfiguracaoOperacional
from .historico_planejamento import HistoricoPlanejamento


__all__ = [
    'db',
    'Usuario',
    'Cliente', 'Usina',
    'Material', 'Servico', 'Categoria', 'Parametro', 'Modalidade',
    'Chamado', 'ChamadoLog', 'ChamadoAnexo', 'ChamadoLembrete',
    'Orcamento', 'OrcamentoMaterial', 'OrcamentoServico',
    'OrdenServico', 'OrdemServicoItem',
    'SystemUpdate',
    'ClienteAcessoSolarz',
    'ConfiguracaoOperacional',
    'HistoricoPlanejamento'
]

