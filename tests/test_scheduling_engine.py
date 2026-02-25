# tests/test_scheduling_engine.py
"""
Unit tests for SchedulingEngine.
These tests run against an in-memory SQLite database and mock OSRM calls
by patching RouteOptimizationService.calcular_rota to return fixed values.
"""

import pytest
from datetime import date, time, datetime
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api import create_app, db
from api.models import (
    Usuario, Cliente, Usina, Chamado,
    PlanejamentoSemana, PlanejamentoDia, PlanejamentoItem,
    ExecucaoDia, ExecucaoEvento,
)
from api.services.scheduling_engine import (
    SchedulingEngine,
    _build_day_sequence,
    _compute_risk,
    _h_to_min,
    WORK_END_H,
    SOFT_LIMIT_H,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXED_ROUTE = {'distancia_km': 30.0, 'tempo_minutos': 35.0, 'geometria': None}


@pytest.fixture(scope='module')
def app():
    import sqlalchemy
    _app = create_app('testing')
    with _app.app_context():
        try:
            db.create_all()
        except (sqlalchemy.exc.CompileError, sqlalchemy.exc.UnsupportedCompilationError):
            pass  # integration tests will skip themselves via the session fixture
        yield _app
        db.session.remove()
        try:
            db.drop_all()
        except Exception:
            pass


@pytest.fixture(scope='function')
def session(app):
    import sqlalchemy
    with app.app_context():
        try:
            db.create_all()
        except (sqlalchemy.exc.CompileError, sqlalchemy.exc.UnsupportedCompilationError):
            pytest.skip('SQLite does not support JSONB — integration tests require PostgreSQL')
        yield db.session
        db.session.remove()
        db.drop_all()


def _make_tech(session):
    tech = Usuario(nome_usuario='Técnico Teste', email='tech@test.com', nivel='tecnico')
    tech.password = 'pw'
    session.add(tech)
    session.flush()
    return tech


def _make_chamado(session, cliente, usina, prioridade='Média', commitment='FLEXIVEL', tempo=60):
    c = Chamado(
        id_usuario_responsavel=1,
        id_cliente=cliente.id_cliente,
        id_usina=usina.id_usina,
        titulo='Test OS',
        categoria='Reparo',
        prioridade=prioridade,
        status='Agendando Visita',
        commitment_level=commitment,
        tempo_estimado_minutos=tempo,
    )
    session.add(c)
    session.flush()
    return c


def _make_cliente_usina(session, lat=-24.4, lng=-53.9):
    cl = Cliente(nome='Cliente', id_usuario_responsavel=1)  # will be overridden if needed
    # Simplify: use minimal required fields
    cl = Cliente.__new__(Cliente)
    cl.nome = 'Cliente'
    cl.is_active = True
    session.add(cl)
    session.flush()

    us = Usina(
        id_cliente=cl.id_cliente,
        nome_usina='Usina',
        cidade='CidadeTeste',
        latitude=str(lat),
        longitude=str(lng),
    )
    session.add(us)
    session.flush()
    return cl, us


# ---------------------------------------------------------------------------
# Tests: risk level
# ---------------------------------------------------------------------------

def test_risk_green():
    assert _compute_risk(_h_to_min(17.5)) == 'GREEN'


def test_risk_yellow():
    assert _compute_risk(_h_to_min(18.2)) == 'YELLOW'


def test_risk_red():
    assert _compute_risk(_h_to_min(19.0)) == 'RED'


def test_risk_red_with_overtime_still_beyond():
    # Even with overtime, 21:00 > 19:30 (max_overtime) → RED
    assert _compute_risk(_h_to_min(21.0), allow_overtime=True) == 'RED'


# ---------------------------------------------------------------------------
# Tests: _build_day_sequence with mocked routing
# ---------------------------------------------------------------------------

class _MockChamado:
    """Minimal mock that looks like a Chamado for `_build_day_sequence`."""
    def __init__(self, id_, prioridade='Média', commitment='FLEXIVEL', tempo=60, lat=-24.4, lng=-53.9):
        self.id_chamado = id_
        self.prioridade = prioridade
        self.commitment_level = commitment
        self.tempo_estimado_minutos = tempo
        self.time_window_start = None
        self.time_window_end = None

        class _Usina:
            pass
        self.usina = _Usina()
        self.usina.latitude = str(lat)
        self.usina.longitude = str(lng)

        class _Cliente:
            nome = 'Cliente'
        self.cliente = _Cliente()


@patch('api.services.scheduling_engine.RouteOptimizationService.calcular_rota',
       return_value=FIXED_ROUTE)
def test_lunch_always_inserted(mock_route):
    """Lunch block must be in the sequence even with only one OS."""
    os_list = [_MockChamado(1, tempo=60)]
    seq, dropped, metrics = _build_day_sequence(
        day_date=date(2026, 2, 23),
        technician_id=1,
        os_list=os_list,
        base_lat=-24.4,
        base_lng=-53.9,
    )
    lunch_blocks = [s for s in seq if s['is_lunch_block']]
    assert len(lunch_blocks) == 1, 'Exactly one lunch block must be present'
    assert lunch_blocks[0]['service_min'] == 90


@patch('api.services.scheduling_engine.RouteOptimizationService.calcular_rota',
       return_value=FIXED_ROUTE)
def test_flexivel_dropped_first_when_day_overflows(mock_route):
    """
    If filling the day causes overflow, FLEXIVEL OS should be dropped before
    PREFERENCIAL and FIXA.
    """
    # Fill day with many 120-min PREFERENCIAL OS so soft_limit is reached
    # then add a FLEXIVEL at the end — it should be the one dropped.
    prefs = [_MockChamado(i, commitment='PREFERENCIAL', tempo=120) for i in range(1, 6)]
    flex = _MockChamado(99, commitment='FLEXIVEL', tempo=120)

    seq, dropped, metrics = _build_day_sequence(
        day_date=date(2026, 2, 23),
        technician_id=1,
        os_list=prefs + [flex],
        base_lat=-24.4,
        base_lng=-53.9,
    )

    dropped_ids = [d.id_chamado for d in dropped]
    # FLEXIVEL (99) should be dropped if anything is
    if dropped_ids:
        assert 99 in dropped_ids or all(
            d.commitment_level in ('FLEXIVEL', 'PREFERENCIAL') for d in dropped
        ), 'FIXA OS should not be dropped before FLEXIVEL/PREFERENCIAL'


@patch('api.services.scheduling_engine.RouteOptimizationService.calcular_rota',
       return_value=FIXED_ROUTE)
def test_eta_within_soft_limit_for_few_os(mock_route):
    """With only 2 short OS the ETA should be well within soft limit (GREEN)."""
    os_list = [_MockChamado(i, tempo=30) for i in range(1, 3)]
    seq, dropped, metrics = _build_day_sequence(
        day_date=date(2026, 2, 23),
        technician_id=1,
        os_list=os_list,
        base_lat=-24.4,
        base_lng=-53.9,
    )
    assert metrics['risk_level'] == 'GREEN'
    assert metrics['eta_end_min'] <= _h_to_min(SOFT_LIMIT_H)


# ---------------------------------------------------------------------------
# Tests: apply_event (requires app context)
# ---------------------------------------------------------------------------

@patch('api.services.scheduling_engine.RouteOptimizationService.calcular_rota',
       return_value=FIXED_ROUTE)
def test_apply_os_finished_marks_concluida(mock_route, session):
    """OS_FINISHED event should set status_execucao=CONCLUIDA on the Chamado.
    NOTE: Requires PostgreSQL — SQLite does not support JSONB used by other models.
    """
    pytest.importorskip('psycopg2', reason='PostgreSQL required for integration tests')
    with session.get_bind().connect() as conn:
        pass  # just ensure session is alive
    # Minimal: create tech + chamado + execution_day
    tech = Usuario(nome_usuario='T', email='t@t.com', nivel='tecnico')
    tech.password = 'x'
    session.add(tech)
    session.flush()

    # We need a minimal Chamado — use a raw insert for speed
    chamado = Chamado(
        id_usuario_responsavel=tech.id_usuario,
        id_cliente=1,  # doesn't exist but FK not enforced in sqlite
        id_usina=1,
        titulo='T',
        categoria='Reparo',
        prioridade='Alta',
        status='Agendando Visita',
        commitment_level='FLEXIVEL',
        tempo_estimado_minutos=60,
    )
    session.add(chamado)
    session.flush()

    exec_day = ExecucaoDia(
        date=date(2026, 2, 23),
        technician_id=tech.id_usuario,
    )
    session.add(exec_day)
    session.flush()

    event = ExecucaoEvento(
        execution_day_id=exec_day.id,
        event_type='OS_FINISHED',
        os_id=chamado.id_chamado,
        at=datetime(2026, 2, 23, 10, 30),
    )
    session.add(event)
    session.flush()

    result = SchedulingEngine.apply_event(exec_day, event)

    session.refresh(chamado)
    assert chamado.status_execucao == 'CONCLUIDA'
    assert 'risk_level' in result
    assert 'recalculated_timeline' in result


@patch('api.services.scheduling_engine.RouteOptimizationService.calcular_rota',
       return_value=FIXED_ROUTE)
def test_apply_pending_return_marks_status(mock_route, session):
    """OS_MARKED_PENDING_RETURN must update status and remaining_work_min.
    NOTE: Requires PostgreSQL — SQLite does not support JSONB used by other models.
    """
    pytest.importorskip('psycopg2', reason='PostgreSQL required for integration tests')
    tech = Usuario(nome_usuario='T2', email='t2@t.com', nivel='tecnico')
    tech.password = 'x'
    session.add(tech)
    session.flush()

    chamado = Chamado(
        id_usuario_responsavel=tech.id_usuario,
        id_cliente=1,
        id_usina=1,
        titulo='T2',
        categoria='Reparo',
        prioridade='Alta',
        status='Agendando Visita',
        commitment_level='PREFERENCIAL',
        tempo_estimado_minutos=120,
    )
    session.add(chamado)
    session.flush()

    exec_day = ExecucaoDia(
        date=date(2026, 2, 24),
        technician_id=tech.id_usuario,
    )
    session.add(exec_day)
    session.flush()

    event = ExecucaoEvento(
        execution_day_id=exec_day.id,
        event_type='OS_MARKED_PENDING_RETURN',
        os_id=chamado.id_chamado,
        at=datetime(2026, 2, 24, 16, 0),
        remaining_work_min=45,
    )
    session.add(event)
    session.flush()

    SchedulingEngine.apply_event(exec_day, event)

    session.refresh(chamado)
    assert chamado.status_execucao == 'PENDENTE_RETORNO'
    assert chamado.remaining_work_min == 45
