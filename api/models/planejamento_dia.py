# /api/models/planejamento_dia.py

from .base import db


class PlanejamentoDia(db.Model):
    """Daily plan within a weekly schedule."""
    __tablename__ = 'planning_day'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(
        db.Integer,
        db.ForeignKey('planning_week.id', ondelete='CASCADE'),
        nullable=False
    )
    date = db.Column(db.Date, nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)

    # Computed metrics (cached after generation/recalculation)
    total_travel_min = db.Column(db.Float, nullable=True)
    total_service_min = db.Column(db.Float, nullable=True)
    total_day_min = db.Column(db.Float, nullable=True)
    total_km = db.Column(db.Float, nullable=True)
    # Estimated end time as minutes-from-midnight for easy comparison
    eta_end_min = db.Column(db.Integer, nullable=True)
    risk_level = db.Column(db.String(10), nullable=True)   # GREEN | YELLOW | RED
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    semana = db.relationship('PlanejamentoSemana', back_populates='days')
    technician = db.relationship('Usuario', foreign_keys=[technician_id])
    items = db.relationship(
        'PlanejamentoItem',
        back_populates='dia',
        cascade='all, delete-orphan',
        order_by='PlanejamentoItem.sequence_index'
    )

    def __repr__(self):
        return f'<PlanejamentoDia date={self.date} risk={self.risk_level}>'
