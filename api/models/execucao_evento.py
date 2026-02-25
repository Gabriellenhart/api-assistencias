# /api/models/execucao_evento.py

from .base import db
from sqlalchemy.sql import func

# Valid event types
EVENT_TYPES = {
    'OS_STARTED',
    'OS_FINISHED',
    'SERVICE_EXTENDED',
    'TRAVEL_DELAY',
    'LUNCH_STARTED',
    'LUNCH_ENDED',
    'OVERTIME_ALLOWED',
    'OS_MARKED_PENDING_RETURN',
    'OS_CANCELED',
}


class ExecucaoEvento(db.Model):
    """
    Immutable event log for a day's execution.
    Events are append-only; the state is derived by replaying them.
    """
    __tablename__ = 'execution_events'

    id = db.Column(db.Integer, primary_key=True)
    execution_day_id = db.Column(
        db.Integer,
        db.ForeignKey('execution_day.id', ondelete='CASCADE'),
        nullable=False
    )

    event_type = db.Column(db.String(40), nullable=False)
    # OS involved (NULL for LUNCH_*, OVERTIME_ALLOWED, TRAVEL_DELAY)
    os_id = db.Column(db.Integer, db.ForeignKey('chamados.id_chamado'), nullable=True)
    # When the event happened (supplied by caller, not server time)
    at = db.Column(db.DateTime(timezone=True), nullable=False)

    # Payload fields (depend on event_type)
    extra_min = db.Column(db.Integer, nullable=True)            # SERVICE_EXTENDED, TRAVEL_DELAY
    remaining_work_min = db.Column(db.Integer, nullable=True)   # OS_MARKED_PENDING_RETURN
    allow_overtime = db.Column(db.Boolean, nullable=True)       # OVERTIME_ALLOWED

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    # Relationships
    execution_day = db.relationship('ExecucaoDia', back_populates='events')
    chamado = db.relationship('Chamado', foreign_keys=[os_id])

    def __repr__(self):
        return f'<ExecucaoEvento type={self.event_type} os={self.os_id} at={self.at}>'
