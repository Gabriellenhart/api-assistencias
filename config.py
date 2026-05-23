# /config.py

import os
from decimal import Decimal
from datetime import timedelta

from dotenv import load_dotenv

# Load environment variables from .env in the project root.
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


def _is_relaxed_env():
    return os.getenv('FLASK_ENV', 'development').lower() in {'development', 'default', 'testing', 'test'}


def _secret(name, development_default):
    value = os.environ.get(name)
    if value:
        return value
    if _is_relaxed_env():
        return development_default
    raise RuntimeError(f"{name} deve ser definida no ambiente de produção.")


def _int_env(name, default):
    value = os.environ.get(name)
    return int(value) if value else default


def _path_env(name, default):
    value = os.environ.get(name)
    if not value:
        return default
    return value if os.path.isabs(value) else os.path.join(basedir, value)


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = _secret('SECRET_KEY', 'dev-secret-key-change-me')
    JWT_SECRET_KEY = _secret('JWT_SECRET_KEY', 'dev-jwt-secret-key-change-me')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=3)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = _path_env('UPLOAD_FOLDER', os.path.join(basedir, 'api', 'static', 'uploads'))
    CHAMADOS_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'chamados')
    ALLOWED_EXTENSIONS = {
        'png', 'jpg', 'jpeg', 'gif', 'jfif', 'pdf', 'doc', 'docx',
        'xls', 'xlsx', 'txt', 'csv', 'zip', 'rar'
    }
    MAX_CONTENT_LENGTH = _int_env('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
    CORS_ORIGINS = os.environ.get(
        'CORS_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000',
    )

    EMPRESA_LONGITUDE = '-53.952700'
    EMPRESA_LATITUDE = '-24.465241'
    CUSTO_POR_KM = Decimal('2.00')


class DevelopmentConfig(Config):
    """Development environment."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DEV_DATABASE_URI')
        or 'postgresql://user:password@localhost/sistema_assistencia_dev'
    )


class TestingConfig(Config):
    """Testing environment (PostgreSQL-only)."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('TEST_DATABASE_URI')
        or 'postgresql://postgres:postgres@localhost:5432/assistencias_test'
    )


class ProductionConfig(Config):
    """Production environment."""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')

    if not SQLALCHEMY_DATABASE_URI and not _is_relaxed_env():
        raise RuntimeError("DATABASE_URI deve ser definida no ambiente de produção.")


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
