# /api/models/planejamento_semana.py

from .base import db
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB


class PlanejamentoSemana(db.Model):
    """Weekly scheduling plan for a single technician."""
    __tablename__ = 'planning_week'
    __table_args__ = (
        db.UniqueConstraint('week_start_date', 'technician_id', name='uq_planning_week_date_tech'),
    )

    id = db.Column(db.Integer, primary_key=True)
    week_start_date = db.Column(db.Date, nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
    # JSON list of chamado IDs that could not be scheduled
    unplanned_os_ids = db.Column(db.JSON, nullable=False, default=list)
    # JSON list of {os_id, reason} for unplanned OS
    unplanned_reasons = db.Column(db.JSON, nullable=False, default=list)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    technician = db.relationship('Usuario', foreign_keys=[technician_id])
    days = db.relationship(
        'PlanejamentoDia',
        back_populates='semana',
        cascade='all, delete-orphan',
        order_by='PlanejamentoDia.date'
    )

    def __repr__(self):
        return f'<PlanejamentoSemana week={self.week_start_date} tech={self.technician_id}>'
