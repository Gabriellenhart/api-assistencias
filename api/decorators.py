# /api/decorators.py (VERSÃO FINAL E CORRIGIDA COM CHECAGEM DE OPTIONS)

from functools import wraps
from flask import jsonify, request # <-- 1. IMPORTAR 'request'
from flask_jwt_extended import verify_jwt_in_request, get_jwt

"""
Este arquivo define os decoradores de permissão personalizados.
Eles agora checam se a requisição é OPTIONS e a deixam passar
para a correta verificação do CORS.
"""

def admin_required():
    """Verifica se o usuário é um 'admin'."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # --- 2. ADICIONA ESTA VERIFICAÇÃO ---
            if request.method == 'OPTIONS':
                return f(*args, **kwargs) # Deixa a requisição OPTIONS passar
                
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('nivel') != 'admin':
                return jsonify({"message": "Acesso restrito a administradores."}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def supervisor_or_admin_required():
    """Verifica se o usuário é 'supervisor' ou 'admin'."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # --- 2. ADICIONA ESTA VERIFICAÇÃO ---
            if request.method == 'OPTIONS':
                return f(*args, **kwargs)

            verify_jwt_in_request()
            claims = get_jwt()
            nivel = claims.get('nivel')
            if nivel not in ['admin', 'supervisor']:
                return jsonify({"message": "Acesso restrito a supervisores e administradores."}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def tecnico_required():
    """Verifica se o usuário é 'tecnico', 'supervisor' ou 'admin' (acesso geral)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # --- 2. ADICIONA ESTA VERIFICAÇÃO ---
            if request.method == 'OPTIONS':
                return f(*args, **kwargs)

            verify_jwt_in_request()
            claims = get_jwt()
            nivel = claims.get('nivel')
            if nivel not in ['admin', 'supervisor', 'tecnico']:
                return jsonify({"message": "Acesso restrito a usuários logados."}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator