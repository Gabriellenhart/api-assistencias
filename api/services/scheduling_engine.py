"""
SchedulingEngine â€” Motor de Planejamento Inteligente de OS

Responsible for:
- Generating weekly plans (Segâ€“Sex) using a greedy nearest-neighbour heuristic
- Evaluating day feasibility, computing metrics and risk level
- Inserting a single OS into an existing day plan
- Applying real-time events and recalculating the remaining day
- Handling PENDENTE_RETORNO (spillover to next day)
"""

import math
import logging
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple

from flask import current_app
from sqlalchemy import or_

from .. import db
from ..models import (
    Chamado,
    OrdenServico,
    Usuario,
    PlanejamentoSemana,
    PlanejamentoDia,
    PlanejamentoItem,
    ExecucaoDia,
    ExecucaoEvento,
)
from .route_optimization_service import RouteOptimizationService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------
WORK_START_H = 8       # 08:00
WORK_END_H = 18        # 18:00
SOFT_LIMIT_H = 18.5    # 18:30
DEFAULT_LUNCH_MIN = 90
LUNCH_WINDOW_START_H = 11.5   # 11:30
LUNCH_WINDOW_END_H = 15.0     # 15:00
DEPARTURE_BUFFER_MIN = 10     # 10 min after shift/lunch start before moving

PRIORITY_WEIGHT = {'URGENTE': 4, 'ALTA': 3, 'MÃ‰DIA': 2, 'MEDIA': 2, 'BAIXA': 1}
COMMITMENT_ORDER = ['FLEXIVEL', 'PREFERENCIAL', 'FIXA']  # cut order

# Greedy cost function weights
ALPHA = 0.3   # weight of service time increment in cost
BETA = 20.0   # weight of priority in cost (higher = priority matters more)
PLANNING_OS_OPEN_STATUSES = ('Aberta', 'Agendado', 'Em Andamento')


def _h_to_min(h: float) -> int:
    """Convert decimal hours to minutes-from-midnight."""
    return int(h * 60)


def _min_to_time(minutes: int) -> time:
    """Convert minutes-from-midnight to a time object (clamped to 23:59)."""
    minutes = max(0, min(minutes, 23 * 60 + 59))
    return time(minutes // 60, minutes % 60)


def _time_to_min(t: time) -> int:
    return t.hour * 60 + t.minute


def _datetime_to_min(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def _priority_value(p: Optional[str]) -> int:
    if p is None:
        return 1
    return PRIORITY_WEIGHT.get(p.upper() if p else '', 1)


def _next_weekday(from_date: date) -> date:
    """Return the next Segâ€“Sex day after from_date (skipping weekends)."""
    d = from_date + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


# ---------------------------------------------------------------------------
# Route cache (in-process, TTL-less for simplicity; reset on restart)
# ---------------------------------------------------------------------------
_route_cache: Dict[str, Dict] = {}


def _get_route(lat1: float, lng1: float, lat2: float, lng2: float) -> Dict:
    """Cached route lookup. Key is rounded to 3 decimal places (~111m grid)."""
    key = f"{round(lat1,3)},{round(lng1,3)}-{round(lat2,3)},{round(lng2,3)}"
    if key not in _route_cache:
        _route_cache[key] = RouteOptimizationService.calcular_rota(
            {'latitude': lat1, 'longitude': lng1},
            {'latitude': lat2, 'longitude': lng2},
        )
    return _route_cache[key]


# ---------------------------------------------------------------------------
# Internal day-builder helpers
# ---------------------------------------------------------------------------

def _serialize_item(item: PlanejamentoItem) -> Dict:
    # Backward/forward-compatible shape for frontend timeline rendering.
    if item.is_lunch_block:
        item_type = 'LUNCH'
    elif item.is_return_continuation:
        item_type = 'CONTINUATION'
    else:
        item_type = 'OS_VISIT'

    planned_start = item.planned_start_at.strftime('%H:%M') if item.planned_start_at else None
    planned_end = item.planned_end_at.strftime('%H:%M') if item.planned_end_at else None

    cliente_nome = None
    status_execucao = None
    prioridade = None
    cidade = None
    id_ordem_servico = None
    if item.chamado:
        cliente_nome = item.chamado.cliente.nome if item.chamado.cliente else None
        status_execucao = item.chamado.status_execucao
        prioridade = item.chamado.prioridade
        cidade = item.chamado.usina.cidade if item.chamado.usina else None
        os_row = (
            OrdenServico.query
            .filter_by(id_chamado=item.chamado.id_chamado)
            .order_by(OrdenServico.id_orden_servico.desc())
            .first()
        )
        if os_row:
            id_ordem_servico = os_row.id_orden_servico

    return {
        'id': item.id,
        'os_id': item.os_id,
        'id_ordem_servico': id_ordem_servico,
        'technician_id': item.dia.technician_id if item.dia else None,
        'technician_name': (
            item.dia.technician.nome_usuario
            if item.dia and item.dia.technician else None
        ),
        'sequence_index': item.sequence_index,
        'item_type': item_type,
        'planned_start': planned_start,
        'planned_end': planned_end,
        'planned_duration_min': item.planned_service_min,
        'travel_min': item.planned_travel_min_from_prev,
        'distance_km': item.planned_km_from_prev,
        'cliente': cliente_nome,
        'status_execucao': status_execucao,
        'prioridade': prioridade,
        'cidade': cidade,
        'planned_start_at': item.planned_start_at.isoformat() if item.planned_start_at else None,
        'planned_end_at': item.planned_end_at.isoformat() if item.planned_end_at else None,
        'planned_service_min': item.planned_service_min,
        'planned_travel_min_from_prev': item.planned_travel_min_from_prev,
        'planned_km_from_prev': item.planned_km_from_prev,
        'is_lunch_block': item.is_lunch_block,
        'is_return_continuation': item.is_return_continuation,
        'commitment_level': item.commitment_level,
    }


def _serialize_day(day: PlanejamentoDia) -> Dict:
    return {
        'id': day.id,
        'date': day.date.isoformat(),
        'technician_id': day.technician_id,
        'total_travel_min': day.total_travel_min,
        'total_service_min': day.total_service_min,
        'total_day_min': day.total_day_min,
        'total_km': day.total_km,
        # compatibility key expected by current frontend widgets
        'total_distance_km': day.total_km,
        'eta_end': _min_to_time(day.eta_end_min).strftime('%H:%M') if day.eta_end_min else None,
        'risk_level': day.risk_level,
        'notes': day.notes,
        'items': [_serialize_item(i) for i in day.items],
    }


def _compute_risk(eta_end_min: int, allow_overtime: bool = False) -> str:
    if eta_end_min <= _h_to_min(WORK_END_H):
        return 'GREEN'
    elif eta_end_min <= _h_to_min(SOFT_LIMIT_H):
        return 'YELLOW'
    else:
        return 'RED'


def _best_lunch_slot(
    items_before_lunch: List[Dict],
    lunch_min: int = DEFAULT_LUNCH_MIN,
) -> int:
    """
    Given a list of tentative items (without lunch), return the sequence index
    (0-based) *after which* to insert the lunch block.

    Strategy: find the index where inserting lunch keeps it inside
    LUNCH_WINDOW_START_Hâ€“LUNCH_WINDOW_END_H. If no slot exists, insert
    after the last item before 15:00.
    """
    best_idx = None
    for idx, item in enumerate(items_before_lunch):
        end_min = item.get('end_min', 0)
        if _h_to_min(LUNCH_WINDOW_START_H) <= end_min <= _h_to_min(LUNCH_WINDOW_END_H):
            best_idx = idx
    if best_idx is None:
        # fallback: insert after last item whose end is before 15:00
        for idx, item in enumerate(items_before_lunch):
            if item.get('end_min', 0) <= _h_to_min(LUNCH_WINDOW_END_H):
                best_idx = idx
    return best_idx if best_idx is not None else len(items_before_lunch) - 1


# ---------------------------------------------------------------------------
# Core build-day function
# ---------------------------------------------------------------------------

def _build_day_sequence(
    day_date: date,
    technician_id: int,
    os_list: List[Chamado],
    base_lat: float,
    base_lng: float,
    constraints: Optional[Dict] = None,
    allow_overtime: bool = False,
    preserve_order: bool = False,
) -> Tuple[List[Dict], List[Chamado], Dict]:
    """
    Greedy nearest-neighbour scheduler for a single day.

    Returns:
        sequence: list of scheduled dicts (os + lunch blocks)
        dropped: list of Chamado objects that didn't fit
        metrics: dict with totals
    """
    constraints = constraints or {}
    work_start_min = _h_to_min(constraints.get('work_start_h', WORK_START_H))
    soft_limit_min = _h_to_min(constraints.get('soft_limit_h', SOFT_LIMIT_H))
    max_ot_min = _h_to_min(constraints.get('max_overtime_h', 19.5))
    end_limit_min = max_ot_min if allow_overtime else soft_limit_min
    lunch_min = constraints.get('lunch_min', DEFAULT_LUNCH_MIN)
    departure_buf = constraints.get('departure_buffer_min', DEPARTURE_BUFFER_MIN)

    # Current clock starts after departure buffer
    current_min = work_start_min + departure_buf
    current_lat, current_lng = base_lat, base_lng

    remaining = list(os_list)
    sequence: List[Dict] = []
    dropped: List[Chamado] = []
    lunch_inserted = False

    total_travel = 0.0
    total_service = 0.0
    total_km = 0.0

    while remaining:
        # --- Try to insert lunch before it gets too late ---
        if not lunch_inserted and current_min >= _h_to_min(LUNCH_WINDOW_START_H):
            lunch_start = current_min
            lunch_end = lunch_start + lunch_min
            sequence.append({
                'os_id': None,
                'is_lunch_block': True,
                'start_min': lunch_start,
                'end_min': lunch_end,
                'service_min': lunch_min,
                'travel_min': 0.0,
                'km': 0.0,
                'commitment_level': None,
                'lat': current_lat,
                'lng': current_lng,
            })
            current_min = lunch_end + departure_buf  # re-depart after lunch
            lunch_inserted = True

        # --- Pick next OS ---
        best_cost = float('inf')
        best_os = None
        best_route = None

        if preserve_order:
            # Manual ordering mode: always try the first OS in the provided list.
            candidate = remaining[0]
            if not candidate.usina or not candidate.usina.latitude or not candidate.usina.longitude:
                remaining.remove(candidate)
                dropped.append(candidate)
                continue
            try:
                os_lat = float(candidate.usina.latitude)
                os_lng = float(candidate.usina.longitude)
            except (TypeError, ValueError):
                remaining.remove(candidate)
                dropped.append(candidate)
                continue

            best_os = candidate
            best_route = _get_route(current_lat, current_lng, os_lat, os_lng)
        else:
            # Greedy optimization mode (automatic generation)
            for os in remaining:
                if not os.usina or not os.usina.latitude or not os.usina.longitude:
                    continue
                try:
                    os_lat = float(os.usina.latitude)
                    os_lng = float(os.usina.longitude)
                except (TypeError, ValueError):
                    continue

                route = _get_route(current_lat, current_lng, os_lat, os_lng)
                travel = route['tempo_minutos']
                service = os.tempo_estimado_minutos or 120
                prio = _priority_value(os.prioridade)

                cost = travel + ALPHA * service - BETA * prio
                if cost < best_cost:
                    best_cost = cost
                    best_os = os
                    best_route = route

        if best_os is None:
            # No more OS with valid geo â€” drop the rest
            dropped.extend(remaining)
            break

        # --- Check if OS fits within limit ---
        service_min = best_os.tempo_estimado_minutos or 120
        travel_min = best_route['tempo_minutos']
        arrival_min = current_min + travel_min
        finish_min = arrival_min + service_min

        # Respect FIXA time window
        if best_os.commitment_level == 'FIXA' and best_os.time_window_start:
            tw_start = _time_to_min(best_os.time_window_start)
            tw_end = _time_to_min(best_os.time_window_end) if best_os.time_window_end else end_limit_min
            if arrival_min > tw_end or finish_min < tw_start:
                # FIXA time window violated â€” skip for now (will remain in dropped)
                remaining.remove(best_os)
                dropped.append(best_os)
                continue
            # Possibly wait for window to open
            if arrival_min < tw_start:
                arrival_min = tw_start
                finish_min = arrival_min + service_min

        # "Don't start what you can't finish" policy
        if finish_min > end_limit_min:
            if preserve_order:
                remaining.remove(best_os)
                dropped.append(best_os)
                continue

            # Apply cut policy: drop lowest-commitment first
            # If this OS itself is the least committed, drop it and try next
            removable = sorted(
                remaining,
                key=lambda o: (COMMITMENT_ORDER.index(o.commitment_level or 'FLEXIVEL'), -_priority_value(o.prioridade))
            )
            if removable and removable[0] != best_os or finish_min > end_limit_min + 60:
                to_drop = removable[0]
                remaining.remove(to_drop)
                dropped.append(to_drop)
                continue
            else:
                # The best OS itself doesn't fit; drop remaining
                dropped.extend(remaining)
                break

        # --- Schedule the OS ---
        sequence.append({
            'os_id': best_os.id_chamado,
            'is_lunch_block': False,
            'is_return_continuation': False,
            'start_min': arrival_min,
            'end_min': finish_min,
            'service_min': service_min,
            'travel_min': travel_min,
            'km': best_route['distancia_km'],
            'commitment_level': best_os.commitment_level or 'FLEXIVEL',
            'lat': float(best_os.usina.latitude),
            'lng': float(best_os.usina.longitude),
        })

        current_min = finish_min
        current_lat = float(best_os.usina.latitude)
        current_lng = float(best_os.usina.longitude)
        total_travel += travel_min
        total_service += service_min
        total_km += best_route['distancia_km']
        remaining.remove(best_os)

    # Ensure lunch is always inserted (even if no OS left)
    if not lunch_inserted:
        lunch_slot_after = max(0, len(sequence) - 1)
        lunch_start = max(current_min, _h_to_min(LUNCH_WINDOW_START_H))
        lunch_end = lunch_start + lunch_min
        sequence.insert(lunch_slot_after + 1, {
            'os_id': None,
            'is_lunch_block': True,
            'start_min': lunch_start,
            'end_min': lunch_end,
            'service_min': lunch_min,
            'travel_min': 0.0,
            'km': 0.0,
            'commitment_level': None,
            'lat': current_lat,
            'lng': current_lng,
        })
        current_min = lunch_end

    eta_end_min = current_min
    total_day_min = total_travel + total_service + lunch_min

    metrics = {
        'total_travel_min': round(total_travel, 1),
        'total_service_min': round(total_service, 1),
        'total_day_min': round(total_day_min, 1),
        'total_km': round(total_km, 2),
        'eta_end_min': eta_end_min,
        'risk_level': _compute_risk(eta_end_min, allow_overtime),
    }

    return sequence, dropped, metrics


def _sequence_to_db_items(
    sequence: List[Dict],
    day_date: date,
    day_id: int,
) -> List[PlanejamentoItem]:
    """Convert the raw sequence dicts to PlanejamentoItem ORM objects."""
    items = []
    tz_offset = timedelta(hours=0)  # store as UTC; frontend adds tz
    day_dt = datetime(day_date.year, day_date.month, day_date.day)

    for idx, s in enumerate(sequence):
        start_dt = day_dt + timedelta(minutes=s['start_min']) if s.get('start_min') is not None else None
        end_dt = day_dt + timedelta(minutes=s['end_min']) if s.get('end_min') is not None else None

        item = PlanejamentoItem(
            day_id=day_id,
            os_id=s.get('os_id'),
            sequence_index=idx,
            planned_start_at=start_dt,
            planned_end_at=end_dt,
            planned_service_min=s.get('service_min'),
            planned_travel_min_from_prev=s.get('travel_min'),
            planned_km_from_prev=s.get('km'),
            is_lunch_block=s.get('is_lunch_block', False),
            is_return_continuation=s.get('is_return_continuation', False),
            commitment_level=s.get('commitment_level'),
        )
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SchedulingEngine:
    """
    Central scheduling motor. All public methods are class-level (no state).
    Database interaction uses the current Flask app context.
    """

    # ------------------------------------------------------------------
    # Week plan generation
    # ------------------------------------------------------------------

    @classmethod
    def generate_week_plan(
        cls,
        week_start_date: date,
        technician_id: int,
        constraints: Optional[Dict] = None,
        force_regenerate: bool = False,
    ) -> Dict:
        """
        Generate (or regenerate) a full Segâ€“Sex plan for one technician.

        Fetches all Chamados with status='Agendando Visita' and no existing
        planning_week association, then fills Monâ€“Fri greedily.

        Returns a serializable dict representing the full Plan.
        """
        # Validate technician
        tech = Usuario.query.get(technician_id)
        if not tech:
            raise ValueError(f"TÃ©cnico {technician_id} nÃ£o encontrado.")

        # Base coordinates (fall back to company coords from config)
        base_lat = float(tech.latitude_base) if getattr(tech, 'latitude_base', None) else float(
            current_app.config.get('EMPRESA_LATITUDE', -24.465241))
        base_lng = float(tech.longitude_base) if getattr(tech, 'latitude_base', None) else float(
            current_app.config.get('EMPRESA_LONGITUDE', -53.952700))

        # Find or create PlanejamentoSemana
        existing = PlanejamentoSemana.query.filter_by(
            week_start_date=week_start_date,
            technician_id=technician_id,
        ).first()

        if existing and not force_regenerate:
            # Return existing plan serialized
            return cls._serialize_week(existing)

        if existing and force_regenerate:
            db.session.delete(existing)
            db.session.flush()

        # Fetch candidate OS from OS table (linked to chamados)
        os_rows = (
            OrdenServico.query
            .join(Chamado, OrdenServico.id_chamado == Chamado.id_chamado)
            .filter(
                OrdenServico.id_chamado.isnot(None),
                OrdenServico.status.in_(PLANNING_OS_OPEN_STATUSES),
                Chamado.is_active == True,
                Chamado.status.in_(['Agendando Visita', 'OS Aberta']),
            )
            .order_by(
                db.case(
                    (Chamado.prioridade == 'URGENTE', 1),
                    (Chamado.prioridade == 'Alta', 2),
                    (Chamado.prioridade == 'MÃ©dia', 3),
                    (Chamado.prioridade == 'Baixa', 4),
                    else_=5
                ),
                Chamado.data_criacao.asc(),
                OrdenServico.id_orden_servico.desc(),
            )
            .all()
        )

        # Keep one active OS per chamado (latest record)
        os_by_chamado_id = {}
        for os_row in os_rows:
            if not os_row.id_chamado:
                continue
            if os_row.id_chamado not in os_by_chamado_id:
                os_by_chamado_id[os_row.id_chamado] = os_row

        os_list_raw = list(os_by_chamado_id.values())

        # Separate plannable vs unplannable (missing geo)
        plannable = []
        unplanned_reasons = []
        for os_row in os_list_raw:
            c = os_row.chamado
            if not c:
                continue
            if not c.usina or not c.usina.latitude or not c.usina.longitude:
                unplanned_reasons.append({
                    'os_id': c.id_chamado,
                    'cliente': c.cliente.nome if c.cliente else '?',
                    'reason': 'missing_geocode',
                })
            else:
                plannable.append(c)

        # Create week record
        semana = PlanejamentoSemana(
            week_start_date=week_start_date,
            technician_id=technician_id,
            unplanned_os_ids=[],
            unplanned_reasons=unplanned_reasons,
        )
        db.session.add(semana)
        db.session.flush()  # get semana.id

        remaining_os = list(plannable)
        days_out = []
        scheduled_chamado_ids = set()

        for day_offset in range(5):  # Mon=0 â€¦ Fri=4
            day_date = week_start_date + timedelta(days=day_offset)
            if not remaining_os:
                break

            sequence, dropped_today, metrics = _build_day_sequence(
                day_date=day_date,
                technician_id=technician_id,
                os_list=remaining_os,
                base_lat=base_lat,
                base_lng=base_lng,
                constraints=constraints,
            )

            # Persist day
            plan_day = PlanejamentoDia(
                plan_id=semana.id,
                date=day_date,
                technician_id=technician_id,
                total_travel_min=metrics['total_travel_min'],
                total_service_min=metrics['total_service_min'],
                total_day_min=metrics['total_day_min'],
                total_km=metrics['total_km'],
                eta_end_min=metrics['eta_end_min'],
                risk_level=metrics['risk_level'],
            )
            db.session.add(plan_day)
            db.session.flush()  # get plan_day.id

            items = _sequence_to_db_items(sequence, day_date, plan_day.id)
            for it in items:
                db.session.add(it)

            days_out.append(plan_day)
            # Remove scheduled OS from remaining
            scheduled_ids = {s['os_id'] for s in sequence if s['os_id']}
            scheduled_chamado_ids |= scheduled_ids
            remaining_os = [o for o in remaining_os if o.id_chamado not in scheduled_ids]

        # Any remaining go to unplanned
        for os in remaining_os:
            semana.unplanned_os_ids = (semana.unplanned_os_ids or []) + [os.id_chamado]
            semana.unplanned_reasons = (semana.unplanned_reasons or []) + [{
                'os_id': os.id_chamado,
                'cliente': os.cliente.nome if os.cliente else '?',
                'reason': 'did_not_fit',
            }]

        # Sync status between OS and chamado according to planning result
        for os_row in os_list_raw:
            c = os_row.chamado
            if not c:
                continue

            is_scheduled = c.id_chamado in scheduled_chamado_ids
            if is_scheduled:
                if os_row.status in ('Aberta', 'Agendado'):
                    os_row.status = 'Agendado'
                if c.status != 'OS Aberta':
                    c.status = 'OS Aberta'
            else:
                if os_row.status == 'Agendado':
                    os_row.status = 'Aberta'
                if c.status == 'OS Aberta':
                    c.status = 'Agendando Visita'

        db.session.commit()

        # Reload with relationships
        db.session.refresh(semana)
        return cls._serialize_week(semana)

    # ------------------------------------------------------------------
    # Week serialization
    # ------------------------------------------------------------------

    @classmethod
    def _serialize_week(cls, semana: PlanejamentoSemana) -> Dict:
        return {
            'plan_id': semana.id,
            'week_start_date': semana.week_start_date.isoformat(),
            'technician_id': semana.technician_id,
            'days': [_serialize_day(d) for d in semana.days],
            'unplanned': semana.unplanned_reasons or [],
            'notes': semana.notes,
        }

    @classmethod
    def serialize_week_view(
        cls,
        week_start_date: date,
        technician_id: Optional[int] = None,
    ) -> Dict:
        """
        Build a week view for one technician OR all technicians combined.
        - If technician_id is provided, returns the stored plan for that technician.
        - If technician_id is None, merges all planning days/items for the given week.
        """
        if technician_id is not None:
            semana = PlanejamentoSemana.query.filter_by(
                week_start_date=week_start_date,
                technician_id=technician_id,
            ).first()
            if not semana:
                raise ValueError('Plano n\u00e3o encontrado. Use POST /planejamento/semana/gerar para criar.')
            return cls._serialize_week(semana)

        week_end = week_start_date + timedelta(days=4)
        days = (
            PlanejamentoDia.query
            .filter(
                PlanejamentoDia.date >= week_start_date,
                PlanejamentoDia.date <= week_end,
            )
            .order_by(PlanejamentoDia.date.asc(), PlanejamentoDia.technician_id.asc())
            .all()
        )

        if not days:
            raise ValueError('Plano n\u00e3o encontrado. Use POST /planejamento/semana/gerar para criar.')

        day_map: Dict[str, Dict] = {}
        for i in range(5):
            d = week_start_date + timedelta(days=i)
            day_map[d.isoformat()] = {
                'id': None,
                'date': d.isoformat(),
                'technician_id': None,
                'total_travel_min': 0.0,
                'total_service_min': 0.0,
                'total_day_min': 0.0,
                'total_km': 0.0,
                'total_distance_km': 0.0,
                'eta_end': None,
                'risk_level': None,
                'notes': None,
                'items': [],
            }

        risk_rank = {'GREEN': 1, 'YELLOW': 2, 'RED': 3, 'OVERTIME': 4}

        for day in days:
            key = day.date.isoformat()
            merged = day_map[key]
            merged['total_travel_min'] += float(day.total_travel_min or 0)
            merged['total_service_min'] += float(day.total_service_min or 0)
            merged['total_day_min'] += float(day.total_day_min or 0)
            merged['total_km'] += float(day.total_km or 0)
            merged['total_distance_km'] += float(day.total_km or 0)

            if day.eta_end_min is not None:
                prev_eta = None
                if merged['eta_end']:
                    hh, mm = merged['eta_end'].split(':')
                    prev_eta = int(hh) * 60 + int(mm)
                if prev_eta is None or day.eta_end_min > prev_eta:
                    merged['eta_end'] = _min_to_time(day.eta_end_min).strftime('%H:%M')

            if day.risk_level:
                prev_rank = risk_rank.get(merged['risk_level'] or '', 0)
                curr_rank = risk_rank.get(day.risk_level, 0)
                if curr_rank >= prev_rank:
                    merged['risk_level'] = day.risk_level

            items_sorted = sorted(day.items, key=lambda it: (it.sequence_index, it.id))
            merged['items'].extend([_serialize_item(it) for it in items_sorted])

        for merged in day_map.values():
            merged['items'].sort(
                key=lambda it: (
                    it.get('planned_start_at') or '',
                    it.get('technician_id') or 0,
                    it.get('sequence_index') or 0,
                )
            )

        semanas = PlanejamentoSemana.query.filter_by(week_start_date=week_start_date).all()
        unplanned = []
        seen_unplanned = set()
        for s in semanas:
            for r in (s.unplanned_reasons or []):
                os_id = r.get('os_id')
                reason = r.get('reason')
                key = (os_id, reason)
                if key in seen_unplanned:
                    continue
                seen_unplanned.add(key)
                unplanned.append(r)

        return {
            'plan_id': None,  # merged view has no single plan_id
            'week_start_date': week_start_date.isoformat(),
            'technician_id': None,
            'days': [day_map[(week_start_date + timedelta(days=i)).isoformat()] for i in range(5)],
            'unplanned': unplanned,
            'notes': None,
        }

    # ------------------------------------------------------------------
    # Move OS between days
    # ------------------------------------------------------------------

    @classmethod
    def move_os(
        cls,
        plan_id: int,
        os_id: int,
        from_date_str: Optional[str],
        to_date_str: Optional[str],
        target_index: Optional[int] = None,
    ) -> Dict:
        """
        Move an OS between days (or unschedule back to backlog) within the same week plan.
        Recalculates all affected days.
        """
        semana = (
            PlanejamentoSemana.query
            .filter_by(id=plan_id)
            .with_for_update()
            .first()
        )
        if not semana:
            raise ValueError(f"Plano {plan_id} nao encontrado.")

        to_date = date.fromisoformat(to_date_str) if to_date_str else None

        chamado = Chamado.query.get(os_id)
        if not chamado:
            raise ValueError(f"Chamado {os_id} nao encontrado.")
        os_row = (
            OrdenServico.query
            .filter_by(id_chamado=chamado.id_chamado)
            .order_by(OrdenServico.id_orden_servico.desc())
            .first()
        )
        if not os_row:
            raise ValueError(f"Nenhuma OS vinculada ao chamado {os_id} foi encontrada.")

        # Remove from unplanned lists if present (if it was previously backlog)
        if semana.unplanned_os_ids and os_id in semana.unplanned_os_ids:
            semana.unplanned_os_ids = [i for i in semana.unplanned_os_ids if i != os_id]
            semana.unplanned_reasons = [
                r for r in (semana.unplanned_reasons or []) if r.get('os_id') != os_id
            ]

        # Remove this OS from every day in the plan (idempotent and duplicate-safe)
        plan_day_ids = [d.id for d in PlanejamentoDia.query.filter_by(plan_id=plan_id).all()]
        affected_day_ids = set()
        if plan_day_ids:
            affected_day_ids = {
                day_id for (day_id,) in (
                    db.session.query(PlanejamentoItem.day_id)
                    .filter(
                        PlanejamentoItem.day_id.in_(plan_day_ids),
                        PlanejamentoItem.os_id == os_id,
                        PlanejamentoItem.is_lunch_block == False,
                    )
                    .distinct()
                    .all()
                )
            }
            if affected_day_ids:
                (
                    PlanejamentoItem.query
                    .filter(
                        PlanejamentoItem.day_id.in_(plan_day_ids),
                        PlanejamentoItem.os_id == os_id,
                        PlanejamentoItem.is_lunch_block == False,
                    )
                    .delete(synchronize_session=False)
                )
                db.session.flush()

                for day_id in affected_day_ids:
                    day = PlanejamentoDia.query.get(day_id)
                    if day:
                        cls._recalculate_day_items(day, semana.technician_id)

        # Unschedule flow: destination is backlog
        if to_date is None:
            if os_id not in (semana.unplanned_os_ids or []):
                semana.unplanned_os_ids = (semana.unplanned_os_ids or []) + [os_id]

            if not any(r.get('os_id') == os_id for r in (semana.unplanned_reasons or [])):
                semana.unplanned_reasons = (semana.unplanned_reasons or []) + [{
                    'os_id': os_id,
                    'cliente': chamado.cliente.nome if chamado.cliente else '?',
                    'reason': 'manual_unschedule',
                }]

            # Backlog => OS volta para aberta e chamado volta para fila de agendamento
            if os_row.status == 'Agendado':
                os_row.status = 'Aberta'
            if chamado.status == 'OS Aberta':
                chamado.status = 'Agendando Visita'

            db.session.commit()
            db.session.refresh(semana)
            return cls._serialize_week(semana)

        to_day = (
            PlanejamentoDia.query
            .filter_by(plan_id=plan_id, date=to_date)
            .with_for_update()
            .first()
        )

        if not to_day:
            to_day = PlanejamentoDia(
                plan_id=plan_id,
                date=to_date,
                technician_id=semana.technician_id,
            )
            db.session.add(to_day)
            db.session.flush()

        tech = Usuario.query.get(semana.technician_id)
        base_lat = float(getattr(tech, 'latitude_base', None) or current_app.config.get('EMPRESA_LATITUDE', -24.465241))
        base_lng = float(getattr(tech, 'longitude_base', None) or current_app.config.get('EMPRESA_LONGITUDE', -53.952700))

        existing_day_items = (
            PlanejamentoItem.query
            .filter_by(day_id=to_day.id)
            .filter(PlanejamentoItem.is_lunch_block == False)
            .order_by(PlanejamentoItem.sequence_index.asc(), PlanejamentoItem.id.asc())
            .all()
        )
        existing_os_ids = [i.os_id for i in existing_day_items if i.os_id]
        # Deduplicate existing ids while preserving order
        seen_existing = set()
        existing_os_ids = [oid for oid in existing_os_ids if not (oid in seen_existing or seen_existing.add(oid))]
        existing_raw = Chamado.query.filter(Chamado.id_chamado.in_(existing_os_ids)).all()
        chamado_map = {c.id_chamado: c for c in existing_raw}
        existing_chamados = [chamado_map[oid] for oid in existing_os_ids if oid in chamado_map and oid != os_id]

        if target_index is not None:
            safe_index = max(0, min(int(target_index), len(existing_chamados)))
            existing_chamados.insert(safe_index, chamado)
        else:
            existing_chamados.append(chamado)

        (
            PlanejamentoItem.query
            .filter_by(day_id=to_day.id)
            .delete(synchronize_session=False)
        )
        db.session.flush()

        sequence, _, metrics = _build_day_sequence(
            day_date=to_date,
            technician_id=semana.technician_id,
            os_list=existing_chamados,
            base_lat=base_lat,
            base_lng=base_lng,
            preserve_order=True,
        )

        new_items = _sequence_to_db_items(sequence, to_date, to_day.id)
        for it in new_items:
            db.session.add(it)
        db.session.flush()

        to_day.total_travel_min = metrics['total_travel_min']
        to_day.total_service_min = metrics['total_service_min']
        to_day.total_day_min = metrics['total_day_min']
        to_day.total_km = metrics['total_km']
        to_day.eta_end_min = metrics['eta_end_min']
        to_day.risk_level = metrics['risk_level']

        # Ao agendar em um dia da semana, sincroniza os status de OS e chamado
        if os_row.status in ('Aberta', 'Agendado'):
            os_row.status = 'Agendado'
        if chamado.status != 'OS Aberta':
            chamado.status = 'OS Aberta'

        db.session.commit()
        db.session.refresh(semana)
        return cls._serialize_week(semana)
    @classmethod
    def _recalculate_day_items(cls, day: PlanejamentoDia, technician_id: int):
        """Rebuild a day plan after manual item removal/insertion and recalculate all metrics."""
        os_items = (
            PlanejamentoItem.query
            .filter_by(day_id=day.id)
            .filter(
                PlanejamentoItem.is_lunch_block == False,
                PlanejamentoItem.os_id.isnot(None),
            )
            .order_by(PlanejamentoItem.sequence_index.asc(), PlanejamentoItem.id.asc())
            .all()
        )
        os_ids = [i.os_id for i in os_items]
        # Ensure one entry per OS id while preserving visual order in the day.
        seen = set()
        os_ids = [oid for oid in os_ids if oid and not (oid in seen or seen.add(oid))]

        # Recalculate route/times from scratch preserving current OS ordering
        tech = Usuario.query.get(technician_id)
        base_lat = float(getattr(tech, 'latitude_base', None) or current_app.config.get('EMPRESA_LATITUDE', -24.465241))
        base_lng = float(getattr(tech, 'longitude_base', None) or current_app.config.get('EMPRESA_LONGITUDE', -53.952700))

        chamados = Chamado.query.filter(Chamado.id_chamado.in_(os_ids)).all()
        chamado_map = {c.id_chamado: c for c in chamados}
        ordered_chamados = [chamado_map[oid] for oid in os_ids if oid in chamado_map]

        sequence, _, metrics = _build_day_sequence(
            day_date=day.date,
            technician_id=technician_id,
            os_list=ordered_chamados,
            base_lat=base_lat,
            base_lng=base_lng,
            preserve_order=True,
        )

        # Replace all items for this day with the recalculated sequence
        (
            PlanejamentoItem.query
            .filter_by(day_id=day.id)
            .delete(synchronize_session=False)
        )
        db.session.flush()

        new_items = _sequence_to_db_items(sequence, day.date, day.id)
        for it in new_items:
            db.session.add(it)

        day.total_travel_min = metrics['total_travel_min']
        day.total_service_min = metrics['total_service_min']
        day.total_day_min = metrics['total_day_min']
        day.total_km = metrics['total_km']
        day.eta_end_min = metrics['eta_end_min']
        day.risk_level = metrics['risk_level']

    # ------------------------------------------------------------------
    # Real-time event application
    # ------------------------------------------------------------------

    @classmethod
    def apply_event(cls, execution_day: ExecucaoDia, event: ExecucaoEvento) -> Dict:
        """
        Apply a new execution event and recalculate the day's remaining timeline.

        Returns:
            {
                updated_execution_day: {...},
                recalculated_timeline: [...],
                risk_level: 'GREEN'|'YELLOW'|'RED',
                suggestions: [...],
            }
        """
        et = event.event_type
        at_min = _datetime_to_min(event.at)

        # --- Update execution day state ---
        if et == 'OS_STARTED':
            execution_day.current_os_id = event.os_id
            if event.os_id:
                chamado = Chamado.query.get(event.os_id)
                if chamado:
                    chamado.status_execucao = 'EM_EXECUCAO'

        elif et == 'OS_FINISHED':
            execution_day.current_os_id = None
            if event.os_id:
                chamado = Chamado.query.get(event.os_id)
                if chamado:
                    chamado.status_execucao = 'CONCLUIDA'

        elif et == 'OS_MARKED_PENDING_RETURN':
            execution_day.current_os_id = None
            if event.os_id:
                chamado = Chamado.query.get(event.os_id)
                if chamado:
                    chamado.status_execucao = 'PENDENTE_RETORNO'
                    chamado.remaining_work_min = event.remaining_work_min

            # Schedule continuation block on next weekday
            next_day = _next_weekday(execution_day.date)
            cls._insert_continuation_block(execution_day, event.os_id, next_day)

        elif et == 'LUNCH_STARTED':
            execution_day.lunch_start_at = event.at

        elif et == 'LUNCH_ENDED':
            execution_day.lunch_end_at = event.at

        elif et == 'OVERTIME_ALLOWED':
            execution_day.allow_overtime_today = bool(event.allow_overtime)

        elif et in ('SERVICE_EXTENDED', 'TRAVEL_DELAY'):
            pass  # handled in timeline recalculation below

        elif et == 'OS_CANCELED':
            if event.os_id:
                chamado = Chamado.query.get(event.os_id)
                if chamado:
                    chamado.status_execucao = 'CONCLUIDA'  # treat as done for the day

        db.session.flush()

        # --- Recalculate remaining timeline ---
        timeline, risk, suggestions = cls._recalculate_remaining(execution_day)
        execution_day.derived_timeline = timeline
        db.session.commit()

        return {
            'updated_execution_day': cls._serialize_exec_day(execution_day),
            'recalculated_timeline': timeline,
            'risk_level': risk,
            'suggestions': suggestions,
        }

    @classmethod
    def _recalculate_remaining(
        cls,
        exec_day: ExecucaoDia,
    ) -> Tuple[List[Dict], str, List[Dict]]:
        """
        Walk through all events chronologically to derive the current state,
        then project the remaining planned items forward.
        """
        events = sorted(exec_day.events, key=lambda e: e.at)

        # Replay events to find current clock and overridden times
        current_min = _time_to_min(exec_day.work_start_admin) + DEPARTURE_BUFFER_MIN
        completed_os_ids = set()
        extra_time: Dict[int, int] = {}  # os_id â†’ extra minutes absorbed so far

        for ev in events:
            ev_min = _datetime_to_min(ev.at)
            if ev.event_type == 'OS_STARTED':
                current_min = ev_min
            elif ev.event_type == 'OS_FINISHED':
                current_min = ev_min
                if ev.os_id:
                    completed_os_ids.add(ev.os_id)
            elif ev.event_type == 'OS_MARKED_PENDING_RETURN':
                current_min = ev_min
                if ev.os_id:
                    completed_os_ids.add(ev.os_id)
            elif ev.event_type == 'LUNCH_ENDED':
                current_min = ev_min + DEPARTURE_BUFFER_MIN
            elif ev.event_type == 'SERVICE_EXTENDED' and ev.os_id:
                extra_time[ev.os_id] = extra_time.get(ev.os_id, 0) + (ev.extra_min or 0)
            elif ev.event_type == 'TRAVEL_DELAY':
                current_min += ev.extra_min or 0

        # Build projected remaining from plan_day items
        if not exec_day.plan_day:
            return [], 'GREEN', []

        remaining_items = [
            i for i in sorted(exec_day.plan_day.items, key=lambda x: x.sequence_index)
            if i.os_id not in completed_os_ids
        ]

        soft_limit_min = _time_to_min(exec_day.soft_limit_end)
        max_end_min = (
            _time_to_min(exec_day.max_overtime_end)
            if exec_day.allow_overtime_today else soft_limit_min
        )

        timeline = []
        dropped_suggestions = []

        for item in remaining_items:
            if item.is_lunch_block:
                # Use real lunch if registered, else planned
                if exec_day.lunch_start_at and exec_day.lunch_end_at:
                    start_min = _datetime_to_min(exec_day.lunch_start_at)
                    end_min = _datetime_to_min(exec_day.lunch_end_at)
                else:
                    start_min = max(current_min, _h_to_min(LUNCH_WINDOW_START_H))
                    end_min = start_min + exec_day.default_lunch_duration_min
                current_min = end_min + DEPARTURE_BUFFER_MIN
                timeline.append({
                    'type': 'lunch',
                    'start_min': start_min,
                    'end_min': end_min,
                })
                continue

            service_min = (item.planned_service_min or 120) + extra_time.get(item.os_id or -1, 0)

            # Remaining work for PENDENTE_RETORNO
            if item.os_id:
                ch = Chamado.query.get(item.os_id)
                if ch and ch.status_execucao == 'PENDENTE_RETORNO' and ch.remaining_work_min:
                    service_min = ch.remaining_work_min

            travel_min = item.planned_travel_min_from_prev or 0
            start_min = current_min + travel_min
            end_min = start_min + service_min

            if end_min > max_end_min:
                # Drop this item per cut policy
                dropped_suggestions.append({
                    'os_id': item.os_id,
                    'commitment_level': item.commitment_level,
                    'reason': 'exceeds_day_limit',
                    'suggestion': 'reschedule_next_week',
                })
                continue

            timeline.append({
                'type': 'os',
                'os_id': item.os_id,
                'start_min': start_min,
                'end_min': end_min,
                'service_min': service_min,
                'travel_min': travel_min,
                'commitment_level': item.commitment_level,
            })
            current_min = end_min

        risk = _compute_risk(current_min, exec_day.allow_overtime_today)
        return timeline, risk, dropped_suggestions

    @classmethod
    def _insert_continuation_block(
        cls, exec_day: ExecucaoDia, os_id: Optional[int], target_date: date
    ):
        """
        Insert a return-continuation PlanejamentoItem at the start of the next day's plan.
        Creates the PlanejamentoDia if it doesn't exist within the same week plan.
        """
        if not os_id:
            return

        chamado = Chamado.query.get(os_id)
        if not chamado:
            return

        # Find plan_day for target_date in the same week plan
        if exec_day.plan_day:
            target_day = PlanejamentoDia.query.filter_by(
                plan_id=exec_day.plan_day.plan_id,
                date=target_date,
            ).first()
        else:
            target_day = None

        if not target_day:
            logger.warning(
                f"Cannot insert continuation for OS {os_id}: "
                f"no plan day for {target_date}."
            )
            return

        # Shift existing items forward
        for item in target_day.items:
            item.sequence_index += 1

        service_min = chamado.remaining_work_min or chamado.tempo_estimado_minutos or 120

        continuation = PlanejamentoItem(
            day_id=target_day.id,
            os_id=os_id,
            sequence_index=0,
            planned_service_min=service_min,
            is_lunch_block=False,
            is_return_continuation=True,
            commitment_level='FIXA',  # treat continuation as FIXA
        )
        db.session.add(continuation)
        logger.info(
            f"Inserted continuation block for OS {os_id} on {target_date} (service={service_min}min)"
        )

    # ------------------------------------------------------------------
    # Execution day serialization
    # ------------------------------------------------------------------

    @classmethod
    def _serialize_exec_day(cls, ed: ExecucaoDia) -> Dict:
        return {
            'id': ed.id,
            'date': ed.date.isoformat(),
            'technician_id': ed.technician_id,
            'plan_day_id': ed.plan_day_id,
            'allow_overtime_today': ed.allow_overtime_today,
            'lunch_start_at': ed.lunch_start_at.isoformat() if ed.lunch_start_at else None,
            'lunch_end_at': ed.lunch_end_at.isoformat() if ed.lunch_end_at else None,
            'current_os_id': ed.current_os_id,
        }

    # ------------------------------------------------------------------
    # Convenience: get full execution day with timeline
    # ------------------------------------------------------------------

    @classmethod
    def get_execution_day(cls, execution_day_id: int) -> Dict:
        ed = ExecucaoDia.query.get(execution_day_id)
        if not ed:
            raise ValueError(f"ExecucaoDia {execution_day_id} nÃ£o encontrado.")

        if ed.derived_timeline is None:
            timeline, risk, suggestions = cls._recalculate_remaining(ed)
            ed.derived_timeline = timeline
            db.session.commit()
        else:
            timeline = ed.derived_timeline
            risk = _compute_risk(
                timeline[-1]['end_min'] if timeline else _h_to_min(WORK_END_H),
                ed.allow_overtime_today,
            )
            suggestions = []

        return {
            'execution_day': cls._serialize_exec_day(ed),
            'timeline': timeline,
            'risk_level': risk,
            'suggestions': suggestions,
            'events': [
                {
                    'id': ev.id,
                    'type': ev.event_type,
                    'os_id': ev.os_id,
                    'at': ev.at.isoformat(),
                    'extra_min': ev.extra_min,
                }
                for ev in ed.events
            ],
        }


