from .base import db
from sqlalchemy.sql import func

class HistoricoPlanejamento(db.Model):
    __tablename__ = 'historico_planejamento'
    
    id = db.Column(db.Integer, primary_key=True)
    id_chamado = db.Column(db.Integer, db.ForeignKey('chamados.id_chamado'), nullable=False)
    id_usuario_anterior = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=True)
    id_usuario_novo = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=True)
    data_agendamento_anterior = db.Column(db.DateTime(timezone=True), nullable=True)
    data_agendamento_novo = db.Column(db.DateTime(timezone=True), nullable=True)
    motivo = db.Column(db.String(255), nullable=True)
    usuario_responsavel_mudanca = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    chamado = db.relationship('Chamado', foreign_keys=[id_chamado])
    usuario_ant = db.relationship('Usuario', foreign_keys=[id_usuario_anterior])
    usuario_nov = db.relationship('Usuario', foreign_keys=[id_usuario_novo])
    usuario_mudanca = db.relationship('Usuario', foreign_keys=[usuario_responsavel_mudanca])
    
    def __repr__(self):
        return f"<HistoricoPlanejamento Chamado#{self.id_chamado}>"
