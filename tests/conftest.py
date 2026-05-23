import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg2
from psycopg2 import sql
import pytest
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api import create_app, db
from api.models import Usuario

ROOT_DIR = Path(__file__).resolve().parent.parent


def _get_base_test_uri() -> str:
    return (
        os.environ.get('TEST_DATABASE_URI')
        or os.environ.get('DEV_DATABASE_URI')
        or 'postgresql://postgres:postgres@localhost:5432/assistencias_test'
    )


def _build_temp_db_uri(base_uri: str) -> tuple[str, str]:
    parsed = urlparse(base_uri)
    base_db_name = (parsed.path or '/assistencias_test').lstrip('/')
    temp_db_name = f"{base_db_name}_pytest_{uuid.uuid4().hex[:8]}"
    temp_parsed = parsed._replace(path=f'/{temp_db_name}')
    return urlunparse(temp_parsed), temp_db_name


def _admin_connection_params(base_uri: str) -> dict:
    parsed = urlparse(base_uri)
    admin_db = os.environ.get('TEST_DB_ADMIN_DB', 'postgres')
    return {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'user': parsed.username or 'postgres',
        'password': parsed.password or '',
        'dbname': admin_db,
    }


def _create_database(base_uri: str, db_name: str) -> None:
    params = _admin_connection_params(base_uri)
    with psycopg2.connect(**params) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db_name)))


def _drop_database(base_uri: str, db_name: str) -> None:
    params = _admin_connection_params(base_uri)
    with psycopg2.connect(**params) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                'SELECT pg_terminate_backend(pid) '
                'FROM pg_stat_activity '
                'WHERE datname = %s AND pid <> pg_backend_pid()',
                (db_name,),
            )
            cur.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(db_name)))


def _run_migrations(database_uri: str) -> None:
    alembic_cfg = AlembicConfig(str(ROOT_DIR / 'migrations' / 'alembic.ini'))
    alembic_cfg.set_main_option('script_location', str(ROOT_DIR / 'migrations'))
    alembic_cfg.set_main_option('sqlalchemy.url', database_uri)
    alembic_command.upgrade(alembic_cfg, 'head')


def _truncate_all_tables() -> None:
    # Keep alembic_version untouched.
    for table in reversed(db.metadata.sorted_tables):
        if table.name == 'alembic_version':
            continue
        db.session.execute(table.delete())
    db.session.commit()


@pytest.fixture(scope='session')
def app():
    base_uri = _get_base_test_uri()
    temp_uri, temp_db_name = _build_temp_db_uri(base_uri)
    created = False

    try:
        _create_database(base_uri, temp_db_name)
        created = True
    except psycopg2.OperationalError as exc:
        pytest.skip(
            f'PostgreSQL indisponivel para testes ({exc}). '
            'Inicie o Postgres e configure TEST_DATABASE_URI.'
        )
    os.environ['TEST_DATABASE_URI'] = temp_uri
    os.environ['FLASK_ENV'] = 'testing'

    try:
        _run_migrations(temp_uri)
        flask_app = create_app(config_name='testing')
        with flask_app.app_context():
            yield flask_app
            db.session.remove()
            db.engine.dispose()
    finally:
        if created:
            _drop_database(base_uri, temp_db_name)


@pytest.fixture(scope='session')
def client(app):
    return app.test_client()


@pytest.fixture(scope='function')
def init_database(app):
    with app.app_context():
        _truncate_all_tables()

        admin_primary = Usuario(nome_usuario='Admin Principal', email='admin@email.com', nivel='admin')
        admin_primary.password = '123456'

        admin_secondary = Usuario(nome_usuario='Admin Teste', email='admin@test.com', nivel='admin')
        admin_secondary.password = 'supersecret'

        tecnico = Usuario(nome_usuario='Tecnico Teste', email='tecnico@test.com', nivel='tecnico')
        tecnico.password = 'password123'

        db.session.add_all([admin_primary, admin_secondary, tecnico])
        db.session.commit()

        yield db

        db.session.remove()
        _truncate_all_tables()
