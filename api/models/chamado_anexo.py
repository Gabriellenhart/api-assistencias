
from .base import db
from sqlalchemy.sql import func

class ChamadoAnexo(db.Model):
    __tablename__ = 'chamado_anexos'
    
    id_anexo = db.Column(db.Integer, primary_key=True)
    id_chamado = db.Column(db.Integer, db.ForeignKey('chamados.id_chamado'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=True)
    id_log = db.Column(db.Integer, db.ForeignKey('chamado_logs.id'), nullable=True)
    
    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    tamanho_bytes = db.Column(db.BigInteger, nullable=True)
    data_upload = db.Column(db.DateTime(timezone=True), server_default=func.now())

    chamado = db.relationship('Chamado', back_populates='anexos')
    usuario = db.relationship('Usuario')
    log = db.relationship('ChamadoLog', back_populates='anexos')
