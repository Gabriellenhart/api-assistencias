# /api/models/chamado.py

from .base import db
from sqlalchemy.sql import func

class Chamado(db.Model):
    __tablename__ = 'chamados'
    id_chamado = db.Column(db.Integer, primary_key=True)
    id_usuario_responsavel = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
    id_cliente = db.Column(db.Integer, db.ForeignKey('clientes.id_cliente'), nullable=False)
    id_usina = db.Column(db.Integer, db.ForeignKey('usinas.id_usina'), nullable=False)
    titulo = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text)
    categoria = db.Column(db.String(100), nullable=False)
    prioridade = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Aberto')
    data_agendamento = db.Column(db.DateTime(timezone=True), nullable=True)
    data_criacao = db.Column(db.DateTime(timezone=True), server_default=func.now())
    data_atualizacao = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    # Scheduling fields
    tempo_estimado_minutos = db.Column(db.Integer, nullable=True)
    km_estimado = db.Column(db.Float, nullable=True)

    # Planning engine fields
    # Commitment level: how flexible this OS is for rescheduling
    commitment_level = db.Column(db.String(20), nullable=False, default='FLEXIVEL')  # FIXA | PREFERENCIAL | FLEXIVEL
    # Optional client time window (only enforced for FIXA)
    time_window_start = db.Column(db.Time, nullable=True)
    time_window_end = db.Column(db.Time, nullable=True)

    # Real-time execution tracking
    status_execucao = db.Column(db.String(30), nullable=False, default='NAO_INICIADA')  # NAO_INICIADA | EM_EXECUCAO | PAUSADA | CONCLUIDA | PENDENTE_RETORNO
    tempo_real_min = db.Column(db.Integer, nullable=True)    # cumulative real time (minutes)
    remaining_work_min = db.Column(db.Integer, nullable=True) # estimated remaining when PENDENTE_RETORNO
    
    logs = db.relationship('ChamadoLog', back_populates='chamado', lazy='dynamic', cascade="all, delete-orphan")
    cliente = db.relationship('Cliente', back_populates='chamados')
    usina = db.relationship('Usina', back_populates='chamados')
    usuario = db.relationship('Usuario')
    anexos = db.relationship('ChamadoAnexo', back_populates='chamado', cascade="all, delete-orphan")
    orcamentos = db.relationship('Orcamento', backref='chamado_origem', lazy=True)