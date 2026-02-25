# /api/models/planejamento_item.py

from .base import db


class PlanejamentoItem(db.Model):
    """
    One item in a daily plan sequence.
    Can represent an OS visit, the lunch block, or a return-continuation block.
    """
    __tablename__ = 'planning_items'

    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(
        db.Integer,
        db.ForeignKey('planning_day.id', ondelete='CASCADE'),
        nullable=False
    )
    # NULL when is_lunch_block=True
    os_id = db.Column(db.Integer, db.ForeignKey('chamados.id_chamado'), nullable=True)
    sequence_index = db.Column(db.Integer, nullable=False)

    # Planned timeline (stored as datetime for easy serialization)
    planned_start_at = db.Column(db.DateTime(timezone=True), nullable=True)
    planned_end_at = db.Column(db.DateTime(timezone=True), nullable=True)
    planned_service_min = db.Column(db.Integer, nullable=True)
    planned_travel_min_from_prev = db.Column(db.Float, nullable=True)
    planned_km_from_prev = db.Column(db.Float, nullable=True)

    # Special block flags
    is_lunch_block = db.Column(db.Boolean, nullable=False, default=False)
    is_return_continuation = db.Column(db.Boolean, nullable=False, default=False)

    # Copied from OS for quick decision-making without a join
    commitment_level = db.Column(db.String(20), nullable=True)

    # Relationships
    dia = db.relationship('PlanejamentoDia', back_populates='items')
    chamado = db.relationship('Chamado', foreign_keys=[os_id])

    def __repr__(self):
        if self.is_lunch_block:
            return f'<PlanejamentoItem [ALMOÇO] idx={self.sequence_index}>'
        return f'<PlanejamentoItem os={self.os_id} idx={self.sequence_index}>'
