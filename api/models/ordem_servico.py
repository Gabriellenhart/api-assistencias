# /api/models/ordem_servico.py (VERSÃO CORRIGIDA)

from .base import db # <-- CORREÇÃO: Importa de .base
from sqlalchemy.sql import func

class OrdenServico(db.Model):
    __tablename__ = 'ordens_servico' 

    id_orden_servico = db.Column(db.Integer, primary_key=True)
    id_orcamento = db.Column(db.Integer, db.ForeignKey('orcamentos.id_orcamento'), nullable=True, unique=True)
    id_chamado = db.Column(db.Integer, db.ForeignKey('chamados.id_chamado'), nullable=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey('clientes.id_cliente'), nullable=False)
    id_usina = db.Column(db.Integer, db.ForeignKey('usinas.id_usina'), nullable=False)
    id_usuario_responsavel = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Aberta')
    data_criacao = db.Column(db.DateTime(timezone=True), server_default=func.now())
    data_conclusao = db.Column(db.DateTime(timezone=True), nullable=True)
    
    orcamento = db.relationship('Orcamento', backref='ordem_servico', uselist=False)
    chamado = db.relationship('Chamado')
    cliente = db.relationship('Cliente')
    usina = db.relationship('Usina')
    usuario = db.relationship('Usuario')
    itens = db.relationship('OrdemServicoItem', back_populates='ordem_servico', cascade="all, delete-orphan")

class OrdemServicoItem(db.Model):
    __tablename__ = 'ordem_servico_itens'
    
    id_item_os = db.Column(db.Integer, primary_key=True)
    id_ordem_servico = db.Column(db.Integer, db.ForeignKey('ordens_servico.id_orden_servico'), nullable=False)
    descricao = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    concluido = db.Column(db.Boolean, default=False, nullable=False)
    
    ordem_servico = db.relationship('OrdenServico', back_populates='itens')