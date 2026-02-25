# /api/models/__init__.py

from .base import db

# Modelos existentes
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

# Modelos do Planejador Inteligente
from .planejamento_semana import PlanejamentoSemana
from .planejamento_dia import PlanejamentoDia
from .planejamento_item import PlanejamentoItem
from .execucao_dia import ExecucaoDia
from .execucao_evento import ExecucaoEvento, EVENT_TYPES


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
    'HistoricoPlanejamento',
    # Scheduler
    'PlanejamentoSemana', 'PlanejamentoDia', 'PlanejamentoItem',
    'ExecucaoDia', 'ExecucaoEvento', 'EVENT_TYPES',
]
