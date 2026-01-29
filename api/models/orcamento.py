# /api/models/orcamento.py (VERSÃO CORRIGIDA)

from .base import db # <-- CORREÇÃO: Importa de .base
from sqlalchemy.sql import func

class Orcamento(db.Model):
    __tablename__ = 'orcamentos'
    
    id_orcamento = db.Column(db.Integer, primary_key=True)
    id_chamado = db.Column(db.Integer, db.ForeignKey('chamados.id_chamado'), nullable=True)
    id_usina = db.Column(db.Integer, db.ForeignKey('usinas.id_usina'), nullable=False)
    id_cliente = db.Column(db.Integer, db.ForeignKey('clientes.id_cliente'), nullable=False)
    id_usuario_responsavel = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
    data_criacao = db.Column(db.DateTime(timezone=True), server_default=func.now())
    descricao_servico = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False, default='pendente')
    data_validade = db.Column(db.DateTime(timezone=True))
    valor_total_itens = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    desconto = db.Column(db.Numeric(10, 2), default=0.0)
    valor_deslocamento = db.Column(db.Numeric(10, 2), default=0.0)
    valor_total_final = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    modalidade = db.Column(db.String(50), nullable=True) 
    qtd_tecnicos = db.Column(db.Integer, default=1)
    horas_previstas = db.Column(db.Numeric(5, 2), default=1.0)
    parametros = db.Column(db.JSON, nullable=True) # Para armazenar overrides e potencia_kwp

    cliente = db.relationship("Cliente", back_populates='orcamentos')
    usina = db.relationship("Usina", back_populates='orcamentos')
    usuario = db.relationship("Usuario")
    materiais = db.relationship("OrcamentoMaterial", back_populates="orcamento", cascade="all, delete-orphan")
    servicos = db.relationship("OrcamentoServico", back_populates="orcamento", cascade="all, delete-orphan")
    
class OrcamentoMaterial(db.Model):
    __tablename__ = 'orcamento_materiais'
    id_orcamento_material = db.Column(db.Integer, primary_key=True)
    id_orcamento = db.Column(db.Integer, db.ForeignKey('orcamentos.id_orcamento'), nullable=False)
    id_material = db.Column(db.Integer, db.ForeignKey('materiais.id_material'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario_cobrado = db.Column(db.Numeric(10, 2), nullable=False)
    
    material = db.relationship("Material")
    orcamento = db.relationship("Orcamento", back_populates="materiais")


class OrcamentoServico(db.Model):
    __tablename__ = 'orcamento_servicos'
    id_orcamento_servico = db.Column(db.Integer, primary_key=True)
    id_orcamento = db.Column(db.Integer, db.ForeignKey('orcamentos.id_orcamento'), nullable=False)
    id_servico = db.Column(db.Integer, db.ForeignKey('servicos.id_servico'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    valor_cobrado = db.Column(db.Numeric(10, 2), nullable=False)
    
    orcamento = db.relationship("Orcamento", back_populates="servicos")
    servico = db.relationship("Servico")