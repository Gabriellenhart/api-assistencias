# /api/models/execucao_dia.py

from .base import db
from sqlalchemy.sql import func
import datetime


class ExecucaoDia(db.Model):
    """
    Real-time execution state for a technician on a given day.
    Created when the technician "opens" the day (starts working).
    Tracks actual events and holds a cached/derived timeline.
    """
    __tablename__ = 'execution_day'
    __table_args__ = (
        db.UniqueConstraint('date', 'technician_id', name='uq_execution_day_date_tech'),
    )

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
    # Link to the planning day this execution is based on (nullable: unplanned day)
    plan_day_id = db.Column(db.Integer, db.ForeignKey('planning_day.id'), nullable=True)

    # Base location of the technician for this day
    base_lat = db.Column(db.Float, nullable=True)
    base_lng = db.Column(db.Float, nullable=True)

    # Administrative constraints (can be overridden per day)
    work_start_admin = db.Column(db.Time, nullable=False, default=datetime.time(8, 0))
    work_end_admin = db.Column(db.Time, nullable=False, default=datetime.time(18, 0))
    soft_limit_end = db.Column(db.Time, nullable=False, default=datetime.time(18, 30))
    default_lunch_duration_min = db.Column(db.Integer, nullable=False, default=90)

    # Lunch tracking
    lunch_start_at = db.Column(db.DateTime(timezone=True), nullable=True)
    lunch_end_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Overtime
    allow_overtime_today = db.Column(db.Boolean, nullable=False, default=False)
    max_overtime_end = db.Column(db.Time, nullable=False, default=datetime.time(19, 30))

    # Current state (updated after each event)
    current_os_id = db.Column(db.Integer, db.ForeignKey('chamados.id_chamado'), nullable=True)
    current_lat = db.Column(db.Float, nullable=True)
    current_lng = db.Column(db.Float, nullable=True)

    # Cached recalculated timeline (JSON, invalidated on each event)
    derived_timeline = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    technician = db.relationship('Usuario', foreign_keys=[technician_id])
    plan_day = db.relationship('PlanejamentoDia', foreign_keys=[plan_day_id])
    current_os = db.relationship('Chamado', foreign_keys=[current_os_id])
    events = db.relationship(
        'ExecucaoEvento',
        back_populates='execution_day',
        cascade='all, delete-orphan',
        order_by='ExecucaoEvento.at'
    )

    def __repr__(self):
        return f'<ExecucaoDia date={self.date} tech={self.technician_id}>'
