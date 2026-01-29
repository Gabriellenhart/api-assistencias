# /api/auth/__init__.py

from flask import Blueprint

# Cria um Blueprint chamado 'auth_bp'. 
# O primeiro argumento é o nome do Blueprint.
# O segundo é o nome do módulo ou pacote onde o Blueprint está localizado.
auth_bp = Blueprint('auth', __name__)

# Importa as rotas no final para evitar dependências circulares.
# O Blueprint precisa saber quais rotas pertencem a ele.
from . import routes