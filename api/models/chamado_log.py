# /api/models/chamado_log.py (VERSÃO CORRIGIDA)

from .base import db # <-- CORREÇÃO: Importa de .base
from sqlalchemy.sql import func

class ChamadoLog(db.Model):
    __tablename__ = 'chamado_logs'

    id = db.Column(db.Integer, primary_key=True)
    id_chamado = db.Column(db.Integer, db.ForeignKey('chamados.id_chamado'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())
    tipo_log = db.Column(db.String(20), nullable=False, default='automatico')
    comentario = db.Column(db.Text, nullable=True)
    campo_alterado = db.Column(db.String(50), nullable=True) 
    valor_antigo = db.Column(db.Text, nullable=True)
    valor_novo = db.Column(db.Text, nullable=True)

    usuario = db.relationship('Usuario')
    chamado = db.relationship('Chamado', back_populates='logs')
    anexos = db.relationship('ChamadoAnexo', back_populates='log', cascade="all, delete-orphan")