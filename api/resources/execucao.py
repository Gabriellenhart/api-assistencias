"""
Recursos de Execução em Tempo Real
Endpoints: /execucao/dia/abrir, /execucao/dia/<id>/evento, /execucao/dia/<id>
"""

import logging
import traceback
from datetime import datetime, date

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from .. import db
from ..models import (
    Usuario,
    ExecucaoDia,
    ExecucaoEvento,
    PlanejamentoDia,
    EVENT_TYPES,
)
from ..services.scheduling_engine import SchedulingEngine

execucao_bp = Blueprint('execucao', __name__)
logger = logging.getLogger(__name__)


def _parse_optional_float(value):
    if value is None or value == '':
        return None
    return float(value)


# ---------------------------------------------------------------------------
# POST /execucao/dia/abrir
# ---------------------------------------------------------------------------

@execucao_bp.route('/dia/abrir', methods=['POST'])
@jwt_required()
def abrir_dia():
    """
    Create or reopen an ExecutionDay for a technician on a given date.

    Body JSON:
        {
            "date": "YYYY-MM-DD",
            "technician_id": int,
            "base_lat": float (optional),
            "base_lng": float (optional),
            "allow_overtime_today": bool (optional)
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'erro': 'JSON inválido ou ausente'}), 400

        date_str = data.get('date')
        technician_id = data.get('technician_id')

        if not date_str or not technician_id:
            return jsonify({'erro': 'date e technician_id são obrigatórios'}), 400

        try:
            exec_date = date.fromisoformat(date_str)
        except ValueError:
            return jsonify({'erro': 'Formato de date inválido. Use YYYY-MM-DD'}), 400

        tech = Usuario.query.get(technician_id)
        if not tech:
            return jsonify({'erro': f'Técnico {technician_id} não encontrado'}), 404

        # Resolve base coords
        base_lat = data.get('base_lat', None)
        base_lng = data.get('base_lng', None)
        if base_lat is None:
            base_lat = getattr(tech, 'latitude_base', None)
        if base_lng is None:
            base_lng = getattr(tech, 'longitude_base', None)

        # Backward compatibility: accept both allow_overtime_today and allow_overtime
        allow_overtime_today = data.get('allow_overtime_today', None)
        if allow_overtime_today is None and 'allow_overtime' in data:
            allow_overtime_today = data.get('allow_overtime')

        # Find linked plan day if any
        plan_day = PlanejamentoDia.query.filter_by(
            date=exec_date, technician_id=technician_id
        ).first()

        # Get or create ExecucaoDia (idempotent)
        exec_day = ExecucaoDia.query.filter_by(
            date=exec_date, technician_id=technician_id
        ).first()

        if not exec_day:
            exec_day = ExecucaoDia(
                date=exec_date,
                technician_id=technician_id,
                plan_day_id=plan_day.id if plan_day else None,
                base_lat=_parse_optional_float(base_lat),
                base_lng=_parse_optional_float(base_lng),
                allow_overtime_today=bool(allow_overtime_today) if allow_overtime_today is not None else False,
            )
            db.session.add(exec_day)
            db.session.commit()
            logger.info(f'ExecucaoDia criado: id={exec_day.id} date={exec_date} tech={technician_id}')
        else:
            # Update overrideable fields if supplied
            if allow_overtime_today is not None:
                exec_day.allow_overtime_today = bool(allow_overtime_today)
            if data.get('base_lat', None) is not None:
                exec_day.base_lat = _parse_optional_float(data.get('base_lat'))
            if data.get('base_lng', None) is not None:
                exec_day.base_lng = _parse_optional_float(data.get('base_lng'))
            db.session.commit()

        return jsonify(SchedulingEngine.get_execution_day(exec_day.id)), 200 if exec_day.id else 201

    except Exception:
        logger.error(f'Erro ao abrir dia de execução:\n{traceback.format_exc()}')
        return jsonify({'erro': 'Erro interno do servidor'}), 500


# ---------------------------------------------------------------------------
# POST /execucao/dia/<execution_day_id>/evento
# ---------------------------------------------------------------------------

@execucao_bp.route('/dia/<int:execution_day_id>/evento', methods=['POST'])
@jwt_required()
def registrar_evento(execution_day_id: int):
    """
    Register a real-time execution event and return the recalculated day plan.

    Body JSON:
        {
            "type": str,             # One of EVENT_TYPES
            "at": "ISO8601",         # When the event happened
            "os_id": int,            # Optional
            "extra_min": int,        # Optional (SERVICE_EXTENDED, TRAVEL_DELAY)
            "remaining_work_min": int, # Optional (OS_MARKED_PENDING_RETURN)
            "allow_overtime": bool   # Optional (OVERTIME_ALLOWED)
        }
    """
    try:
        exec_day = ExecucaoDia.query.get(execution_day_id)
        if not exec_day:
            return jsonify({'erro': f'ExecucaoDia {execution_day_id} não encontrado'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'erro': 'JSON inválido ou ausente'}), 400

        event_type = data.get('type')
        if not event_type:
            return jsonify({'erro': '"type" é obrigatório'}), 400
        if event_type not in EVENT_TYPES:
            return jsonify({
                'erro': f'Tipo de evento inválido: {event_type}',
                'tipos_validos': sorted(EVENT_TYPES),
            }), 400

        at_raw = data.get('at')
        if not at_raw:
            return jsonify({'erro': '"at" (timestamp do evento) é obrigatório'}), 400
        try:
            at_dt = datetime.fromisoformat(at_raw)
        except ValueError:
            return jsonify({'erro': 'Formato de "at" inválido. Use ISO 8601 (ex: 2026-02-23T09:30:00)'}), 400

        # Validate event-type-specific required fields
        if event_type in ('SERVICE_EXTENDED', 'TRAVEL_DELAY') and not data.get('extra_min'):
            return jsonify({'erro': f'"extra_min" é obrigatório para {event_type}'}), 400
        if event_type == 'OS_MARKED_PENDING_RETURN' and not data.get('remaining_work_min'):
            return jsonify({'erro': '"remaining_work_min" é obrigatório para OS_MARKED_PENDING_RETURN'}), 400

        # Persist event
        event = ExecucaoEvento(
            execution_day_id=execution_day_id,
            event_type=event_type,
            os_id=data.get('os_id'),
            at=at_dt,
            extra_min=data.get('extra_min'),
            remaining_work_min=data.get('remaining_work_min'),
            allow_overtime=data.get('allow_overtime'),
        )
        db.session.add(event)
        db.session.flush()

        # Apply event and recalculate
        result = SchedulingEngine.apply_event(exec_day, event)
        return jsonify(result), 200

    except ValueError as e:
        return jsonify({'erro': str(e)}), 400
    except Exception:
        logger.error(f'Erro ao registrar evento:\n{traceback.format_exc()}')
        return jsonify({'erro': 'Erro interno do servidor'}), 500


# ---------------------------------------------------------------------------
# GET /execucao/dia/<execution_day_id>
# ---------------------------------------------------------------------------

@execucao_bp.route('/dia/<int:execution_day_id>', methods=['GET'])
@jwt_required()
def obter_dia_execucao(execution_day_id: int):
    """
    Return the full execution day state: timeline, ETA, risk level, suggestions.
    """
    try:
        result = SchedulingEngine.get_execution_day(execution_day_id)
        return jsonify(result), 200

    except ValueError as e:
        return jsonify({'erro': str(e)}), 404
    except Exception:
        logger.error(f'Erro ao obter dia de execução:\n{traceback.format_exc()}')
        return jsonify({'erro': 'Erro interno do servidor'}), 500
