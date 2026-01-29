from .base import db
from sqlalchemy.sql import func

class ChamadoLembrete(db.Model):
    __tablename__ = 'chamado_lembretes'
    
    id_lembrete = db.Column(db.Integer, primary_key=True)
    id_chamado = db.Column(db.Integer, db.ForeignKey('chamados.id_chamado'), nullable=False)
    id_usuario_criador = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
    
    # Novo campo para vincular ao comentário (Log)
    id_chamado_log = db.Column(db.Integer, db.ForeignKey('chamado_logs.id'), nullable=True)

    titulo = db.Column(db.String(255), nullable=False)
    data_lembrete = db.Column(db.DateTime, nullable=False)
    
    status = db.Column(db.String(50), default='pendente') # pendente, concluido
    data_criacao = db.Column(db.DateTime(timezone=True), server_default=func.now())
    data_conclusao = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relacionamentos
    chamado = db.relationship('Chamado', backref=db.backref('lembretes', lazy=True))
    usuario = db.relationship('Usuario')
    # Relacionamento com Log
    chamado_log = db.relationship('ChamadoLog', backref=db.backref('lembretes', lazy='joined'))
