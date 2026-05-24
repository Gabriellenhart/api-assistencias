# /api/__init__.py (VERSÃO FINAL E CORRIGIDA COM CORS)

import os
from flask import Flask, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_marshmallow import Marshmallow
from flask_cors import CORS
import logging
import traceback

from config import config

# 1. Inicializa as extensões (sem app ainda)
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
bcrypt = Bcrypt()
ma = Marshmallow()


def _parse_cors_origins(value, config_name):
    if not value:
        if config_name == 'development':
            return [
                'http://localhost:5173',
                'http://127.0.0.1:5173',
                'http://localhost:3000',
            ]
        return []

    origins = [origin.strip() for origin in value.split(',') if origin.strip()]
    if origins == ['*'] and config_name != 'development':
        raise RuntimeError("CORS_ORIGINS='*' só é permitido em desenvolvimento.")
    return origins


def _validate_production_env():
    missing = [
        name for name in ('SECRET_KEY', 'JWT_SECRET_KEY', 'DATABASE_URI')
        if not os.getenv(name)
    ]
    if missing:
        raise RuntimeError(
            "Variáveis obrigatórias ausentes em produção: " + ", ".join(missing)
        )


def create_app(config_name=None):
    """
    Application Factory: Cria e configura a instância da aplicação Flask.
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    if config_name == 'production':
        _validate_production_env()

    app = Flask(__name__, static_folder='static') 
    app.config.from_object(config[config_name])

    # 2. Associa as extensões à aplicação
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)
    ma.init_app(app)
    
    # Configura CORS para aceitar requisições do frontend
    cors_origins = _parse_cors_origins(app.config.get('CORS_ORIGINS'), config_name)
    CORS(app,
         resources={r"/*": {
             "origins": cors_origins,
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
             "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
         }},
         automatic_options=True,
    )

    # --- 3. Carregamento de Usuário (Importação DENTRO da função) ---
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """
        Importa 'Usuario' AQUI DENTRO para evitar importação circular.
        """
        from .models import Usuario
        
        identity = jwt_data.get("sub")
        if identity is None: 
            return None
        try:
            user_id = int(identity)
            return Usuario.query.get(user_id) 
        except (ValueError, TypeError):
            return None

    # --- 4. Importações de Blueprints e Comandos DENTRO DA FACTORY ---
    
    # Comandos CLI
    from . import commands
    app.cli.add_command(commands.create_admin)
    app.cli.add_command(commands.reset_password)

    # Blueprints (Rotas)
    from .auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .resources.orcamentos import orcamentos_bp
    app.register_blueprint(orcamentos_bp, url_prefix='/orcamentos')
    
    from .resources.chamados import chamados_bp
    app.register_blueprint(chamados_bp, url_prefix='/chamados')

    from .resources.usuarios import usuarios_bp
    app.register_blueprint(usuarios_bp, url_prefix='/usuarios')

    from .resources.clientes import clientes_bp
    app.register_blueprint(clientes_bp, url_prefix='/clientes')

    from .resources.materiais import materiais_bp
    app.register_blueprint(materiais_bp, url_prefix='/materiais')

    from .resources.servicos import servicos_bp
    app.register_blueprint(servicos_bp, url_prefix='/servicos')
    
    from .resources.usinas import usinas_bp
    app.register_blueprint(usinas_bp, url_prefix='/usinas')
    
    from .resources.logs import logs_bp
    app.register_blueprint(logs_bp, url_prefix='/logs')

    from .resources.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard-stats')

    from .resources.ordens_servico import ordens_servico_bp
    app.register_blueprint(ordens_servico_bp, url_prefix='/ordens-servico')

    from .resources.configuracoes import config_bp
    app.register_blueprint(config_bp, url_prefix='/config')

    from .resources.planejamento import planejamento_bp
    app.register_blueprint(planejamento_bp, url_prefix='/planejamento')
    
    from .resources.updates import updates_bp
    app.register_blueprint(updates_bp, url_prefix='/updates')
    
    from .resources.integracoes import integracoes_bp
    app.register_blueprint(integracoes_bp, url_prefix='/integracoes')
    
    from .resources.lembretes import bp as lembretes_bp
    app.register_blueprint(lembretes_bp, url_prefix='/lembretes')

    from .resources.execucao import execucao_bp
    app.register_blueprint(execucao_bp, url_prefix='/execucao')

    from api.resources.briefing import briefing_bp
    app.register_blueprint(briefing_bp, url_prefix="/briefing")
    
    # Rota para servir uploads (avatars, anexos, etc.)
    @app.route('/static/uploads/<path:filename>')
    def serve_uploads(filename):
        # Garante que servimos da pasta api/static/uploads configurada
        upload_root = os.path.join(app.root_path, 'static', 'uploads')
        return send_from_directory(upload_root, filename)
             
    @app.route('/')
    def index():
        return "API do Sistema de Assistência no ar!"

    return app
