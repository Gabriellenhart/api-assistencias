# /config.py

import os
from dotenv import load_dotenv
from decimal import Decimal
from datetime import timedelta

# Carrega as variáveis de ambiente do arquivo .env
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """Configurações base, compartilhadas por todos os ambientes."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma-chave-secreta-dificil-de-adivinhar'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'uma-outra-chave-jwt-muito-segura'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=3)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'api', 'static', 'uploads')
    CHAMADOS_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'chamados')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'jfif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv', 'zip', 'rar'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Limite de 16MB
    EMPRESA_LONGITUDE = "-53.952700"
    EMPRESA_LATITUDE = "-24.465241"
 
   
    # Custo por quilômetro (Ex: R$ 1,50)
    CUSTO_POR_KM = Decimal("2.00")


class DevelopmentConfig(Config):
    """Configurações para o ambiente de desenvolvimento."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URI') or \
        'postgresql://user:password@localhost/sistema_assistencia_dev'

class TestingConfig(Config):
    """Configurações para o ambiente de testes."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URI') or \
        'sqlite:///:memory:' # Testes geralmente usam um banco em memória

class ProductionConfig(Config):
    """Configurações para o ambiente de produção."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI') or \
        'postgresql://user:password@localhost/sistema_assistencia_prod'

# Dicionário para facilitar o acesso às classes de configuração
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}