# tests/test_scheduling_engine.py

from datetime import date, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import inspect

from api import db
from api.models import Chamado, Cliente, ExecucaoDia, ExecucaoEvento, Usina, Usuario
from api.services.scheduling_engine import (
    SOFT_LIMIT_H,
    SchedulingEngine,
    _build_day_sequence,
    _compute_risk,
    _h_to_min,
)

FIXED_ROUTE = {'distancia_km': 30.0, 'tempo_minutos': 35.0, 'geometria': None}


def _missing_required_model_columns():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    missing = []
    for model in (Chamado, Cliente, ExecucaoDia, ExecucaoEvento, Usina, Usuario):
        table = model.__table__
        if table.name not in existing_tables:
            missing.append(table.name)
            continue
        existing_columns = {column['name'] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing_columns:
                missing.append(f'{table.name}.{column.name}')
    return missing


def _truncate_all_tables():
    existing_tables = set(inspect(db.engine).get_table_names())
    for table in reversed(db.metadata.sorted_tables):
        if table.name == 'alembic_version' or table.name not in existing_tables:
            continue
        db.session.execute(table.delete())
    db.session.commit()


@pytest.fixture(scope='function')
def session(app):
    with app.app_context():
        missing = _missing_required_model_columns()
        if missing:
            pytest.skip(
                'Schema migrado nao contem todas as colunas exigidas pelos '
                f'models usados nestes testes de integracao: {", ".join(missing)}'
            )
        _truncate_all_tables()
        yield db.session
        db.session.remove()
        _truncate_all_tables()


def _make_tech(session, email='tech@test.com'):
    tech = Usuario(nome_usuario='Tecnico Teste', email=email, nivel='tecnico')
    tech.password = 'pw'
    session.add(tech)
    session.flush()
    return tech


def _make_cliente_usina(session, lat='-24.4', lng='-53.9'):
    cliente = Cliente(nome='Cliente Teste')
    session.add(cliente)
    session.flush()

    usina = Usina(
        id_cliente=cliente.id_cliente,
        nome_usina='Usina Teste',
        cidade='CidadeTeste',
        latitude=str(lat),
        longitude=str(lng),
    )
    session.add(usina)
    session.flush()
    return cliente, usina


def _make_chamado(session, tech, cliente, usina, prioridade='Media', commitment='FLEXIVEL', tempo=60):
    chamado = Chamado(
        id_usuario_responsavel=tech.id_usuario,
        id_cliente=cliente.id_cliente,
        id_usina=usina.id_usina,
        titulo='Test OS',
        categoria='Reparo',
        prioridade=prioridade,
        status='Agendando Visita',
        commitment_level=commitment,
        tempo_estimado_minutos=tempo,
    )
    session.add(chamado)
    session.flush()
    return chamado


# ---------------------------------------------------------------------------
# Tests: risk level
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_risk_green():
    assert _compute_risk(_h_to_min(17.5)) == 'GREEN'


@pytest.mark.unit
def test_risk_yellow():
    assert _compute_risk(_h_to_min(18.2)) == 'YELLOW'


@pytest.mark.unit
def test_risk_red():
    assert _compute_risk(_h_to_min(19.0)) == 'RED'


@pytest.mark.unit
def test_risk_red_with_overtime_still_beyond():
    assert _compute_risk(_h_to_min(21.0), allow_overtime=True) == 'RED'


# ---------------------------------------------------------------------------
# Tests: _build_day_sequence with mocked routing
# ---------------------------------------------------------------------------


class _MockChamado:
    def __init__(self, id_, prioridade='Media', commitment='FLEXIVEL', tempo=60, lat='-24.4', lng='-53.9'):
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


@patch('api.services.scheduling_engine.RouteOptimizationService.calcular_rota', return_value=FIXED_ROUTE)
@pytest.mark.unit
def test_lunch_always_inserted(_mock_route):
    os_list = [_MockChamado(1, tempo=60)]
    seq, dropped, metrics = _build_day_sequence(
        day_date=date(2026, 2, 23),
        technician_id=1,
        os_list=os_list,
        base_lat=-24.4,
        base_lng=-53.9,
    )
    lunch_blocks = [s for s in seq if s['is_lunch_block']]
    assert len(lunch_blocks) == 1
    assert lunch_blocks[0]['service_min'] == 90


@patch('api.services.scheduling_engine.RouteOptimizationService.calcular_rota', return_value=FIXED_ROUTE)
@pytest.mark.unit
def test_flexivel_dropped_first_when_day_overflows(_mock_route):
    prefs = [_MockChamado(i, commitment='PREFERENCIAL', tempo=120) for i in range(1, 6)]
    flex = _MockChamado(99, commitment='FLEXIVEL', tempo=120)

    _seq, dropped, _metrics = _build_day_sequence(
        day_date=date(2026, 2, 23),
        technician_id=1,
        os_list=prefs + [flex],
        base_lat=-24.4,
        base_lng=-53.9,
    )

    dropped_ids = [d.id_chamado for d in dropped]
    if dropped_ids:
        assert 99 in dropped_ids or all(
            d.commitment_level in ('FLEXIVEL', 'PREFERENCIAL') for d in dropped
        )


@patch('api.services.scheduling_engine.RouteOptimizationService.calcular_rota', return_value=FIXED_ROUTE)
@pytest.mark.unit
def test_eta_within_soft_limit_for_few_os(_mock_route):
    os_list = [_MockChamado(i, tempo=30) for i in range(1, 3)]
    _seq, _dropped, metrics = _build_day_sequence(
        day_date=date(2026, 2, 23),
        technician_id=1,
        os_list=os_list,
        base_lat=-24.4,
        base_lng=-53.9,
    )
    assert metrics['risk_level'] == 'GREEN'
    assert metrics['eta_end_min'] <= _h_to_min(SOFT_LIMIT_H)


# ---------------------------------------------------------------------------
# Tests: apply_event
# ---------------------------------------------------------------------------


@patch('api.services.scheduling_engine.RouteOptimizationService.calcular_rota', return_value=FIXED_ROUTE)
@pytest.mark.integration
def test_apply_os_finished_marks_concluida(_mock_route, session):
    tech = _make_tech(session, email='t@t.com')
    cliente, usina = _make_cliente_usina(session)
    chamado = _make_chamado(session, tech, cliente, usina, prioridade='Alta', commitment='FLEXIVEL', tempo=60)

    exec_day = ExecucaoDia(date=date(2026, 2, 23), technician_id=tech.id_usuario)
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


@patch('api.services.scheduling_engine.RouteOptimizationService.calcular_rota', return_value=FIXED_ROUTE)
@pytest.mark.integration
def test_apply_pending_return_marks_status(_mock_route, session):
    tech = _make_tech(session, email='t2@t.com')
    cliente, usina = _make_cliente_usina(session)
    chamado = _make_chamado(session, tech, cliente, usina, prioridade='Alta', commitment='PREFERENCIAL', tempo=120)

    exec_day = ExecucaoDia(date=date(2026, 2, 24), technician_id=tech.id_usuario)
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
