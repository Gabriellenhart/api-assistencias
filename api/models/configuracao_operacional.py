from .base import db
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

class ConfiguracaoOperacional(db.Model):
    __tablename__ = 'configuracao_operacional'
    
    id = db.Column(db.Integer, primary_key=True)
    margem_seguranca_minutos = db.Column(db.Integer, nullable=False, default=30)
    velocidade_media_kmh = db.Column(db.Numeric(5, 2), nullable=False, default=50.0)
    tempo_medio_por_categoria = db.Column(JSONB, nullable=True)
    feriados = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ConfiguracaoOperacional {self.id}>"
