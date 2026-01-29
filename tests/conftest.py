# /tests/conftest.py

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api import create_app, db
from api.models import Usuario

@pytest.fixture(scope='module')
def app():
    """Fixture que cria uma instância da aplicação Flask para os testes."""
    # Cria a app usando a configuração de teste
    app = create_app(config_name='testing')
    
    with app.app_context():
        # Cria todas as tabelas no banco de dados em memória (SQLite)
        db.create_all()
        
        # 'yield' passa a instância da app para os testes
        yield app
        
        # Código de limpeza: remove o contexto e apaga as tabelas
        db.session.remove()
        db.drop_all()

@pytest.fixture(scope='module')
def client(app):
    """Fixture que cria um cliente de teste para fazer requisições à API."""
    return app.test_client()

@pytest.fixture(scope='function')
def init_database(app):
    with app.app_context():
        db.create_all()
        
        admin = Usuario(nome_usuario='Admin Teste', email='admin@test.com', nivel='admin')
        admin.password = 'supersecret' # <-- MUDANÇA AQUI
        
        tecnico = Usuario(nome_usuario='Tecnico Teste', email='tecnico@test.com', nivel='tecnico')
        tecnico.password = 'password123' # <-- MUDANÇA AQUI
        
        db.session.add(admin)
        db.session.add(tecnico)
        db.session.commit()
        
        yield db
        
        db.session.remove()
        db.drop_all()