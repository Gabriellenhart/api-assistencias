# /api/resources/configuracoes.py (VERSÃO REFATORADA)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
import logging
import traceback
import json
from sqlalchemy import or_ # Importa o 'or_'

from .. import db
from ..models import Categoria, Parametro, Modalidade
from ..schemas.config_schema import CategoriaSchema, ParametroSchema, ModalidadeSchema
from ..decorators import admin_required, tecnico_required, supervisor_or_admin_required

config_bp = Blueprint('configuracoes', __name__)

# --- ROTA DE LEITURA (GET) ---
# Esta rota agora busca TODAS as opções de chamado de uma vez
@config_bp.route('/opcoes-chamado', methods=['GET'])
@jwt_required()
@tecnico_required()
def get_opcoes_chamado():
    """Retorna todas as opções ativas para formulários de chamado."""
    try:
        opcoes = Categoria.query.filter(
            Categoria.is_active == True,
            or_( # Busca todos os tipos que o chamado usa
                Categoria.tipo == 'categoria_chamado',
                Categoria.tipo == 'status_chamado',
                Categoria.tipo == 'prioridade_chamado'
            )
        ).order_by(Categoria.nome).all()
        
        # Separa os resultados em dicionários
        resultado = {
            "categorias": [cat for cat in opcoes if cat.tipo == 'categoria_chamado'],
            "status": [cat for cat in opcoes if cat.tipo == 'status_chamado'],
            "prioridades": [cat for cat in opcoes if cat.tipo == 'prioridade_chamado']
        }
        
        # Converte para JSON usando o schema
        schema = CategoriaSchema(many=True)
        return jsonify({
            "categorias": schema.dump(resultado["categorias"]),
            "status": schema.dump(resultado["status"]),
            "prioridades": schema.dump(resultado["prioridades"])
        }), 200
        
    except Exception as e:
        return jsonify({"message": "Erro ao buscar opções", "error": str(e)}), 500

# --- ROTAS DE ESCRITA (POST, PUT, DELETE) ---
# Estas rotas agora são genéricas para qualquer "Opção"

@config_bp.route('/opcoes', methods=['POST'])
@jwt_required()
@supervisor_or_admin_required()
def create_opcao():
    """Cria uma nova opção (Categoria, Status, etc.)."""
    json_data = request.get_json()
    schema = CategoriaSchema()
    try:
        # Passa a sessão para o 'load'
        data = schema.load(json_data, session=db.session)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400

    if Categoria.query.filter_by(nome=data.nome, tipo=data.tipo).first():
        return jsonify({"message": f"Uma opção com este nome e tipo ('{data.tipo}') já existe."}), 409

    try:
        db.session.add(data)
        db.session.commit()
        return jsonify(schema.dump(data)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao salvar nova opção", "error": str(e)}), 500

@config_bp.route('/opcoes/<int:id_opcao>', methods=['PUT'])
@jwt_required()
@supervisor_or_admin_required()
def update_opcao(id_opcao):
    """Atualiza o nome ou status de uma opção."""
    opcao = Categoria.query.get_or_404(id_opcao)
    json_data = request.get_json()
    
    schema = CategoriaSchema(partial=True)
    try:
        opcao_atualizada = schema.load(
            json_data, 
            session=db.session, 
            instance=opcao
        )
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400

    if 'nome' in json_data:
        novo_nome = json_data['nome']
        existe = Categoria.query.filter(
            Categoria.nome == novo_nome, 
            Categoria.tipo == opcao_atualizada.tipo, # Verifica apenas dentro do mesmo tipo
            Categoria.id_categoria != id_opcao
        ).first()
        if existe:
            return jsonify({"message": "Uma opção com este nome e tipo já existe."}), 409
    
    try:
        db.session.commit()
        return jsonify(schema.dump(opcao_atualizada)), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao atualizar opção", "error": str(e)}), 500

@config_bp.route('/opcoes/<int:id_opcao>', methods=['DELETE'])
@jwt_required()
@admin_required()
def delete_opcao(id_opcao):
    """Desativa (soft delete) uma opção."""
    opcao = Categoria.query.get_or_404(id_opcao)
    opcao.is_active = False 
    try:
        db.session.commit()
        return jsonify({"message": f"Opção '{opcao.nome}' foi arquivada."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao arquivar opção", "error": str(e)}), 500

# --- ROTA AGREGADORA ORÇAMENTO ---
@config_bp.route('/orcamento-configs', methods=['GET'])
@jwt_required()
@tecnico_required()
def get_orcamento_configs():
    """Retorna todas as configurações para orçamentos (Status, Modalidades, Parâmetros)."""
    try:
        status_opts = Categoria.query.filter_by(tipo='status_orcamento', is_active=True).order_by(Categoria.nome).all()
        modalidades = Modalidade.query.filter_by(ativo=True).order_by(Modalidade.nome).all()
        parametros = Parametro.query.filter(Parametro.chave.like('orcamento%')).all()
        
        
        # Processar JSON das modalidades para retorno correto
        modalidades_dump = ModalidadeSchema(many=True).dump(modalidades)
        for m in modalidades_dump:
            if isinstance(m.get('configuracao'), str):
                try: m['configuracao'] = json.loads(m['configuracao'])
                except: pass

        return jsonify({
            "status": CategoriaSchema(many=True).dump(status_opts),
            "modalidades": modalidades_dump,
            "parametros": ParametroSchema(many=True).dump(parametros)
        }), 200
    except Exception as e:
        return jsonify({"message": "Erro ao buscar configs de orçamento", "error": str(e)}), 500

# --- CRUD PARAMETROS ---
@config_bp.route('/parametros', methods=['POST'])
@jwt_required()
@supervisor_or_admin_required()
def create_parametro():
    json_data = request.get_json()
    schema = ParametroSchema()
    try:
        data = schema.load(json_data, session=db.session)
        if Parametro.query.filter_by(chave=data.chave).first():
            return jsonify({"message": f"Parâmetro '{data.chave}' já existe."}), 409
        db.session.add(data)
        db.session.commit()
        return jsonify(schema.dump(data)), 201
    except ValidationError as err:
        return jsonify({"message": "Erro validação", "errors": err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao criar parâmetro", "error": str(e)}), 500

@config_bp.route('/parametros/<int:id_param>', methods=['PUT'])
@jwt_required()
@supervisor_or_admin_required()
def update_parametro(id_param):
    param = Parametro.query.get_or_404(id_param)
    json_data = request.get_json()
    schema = ParametroSchema(partial=True)
    try:
        param = schema.load(json_data, session=db.session, instance=param)
        db.session.commit()
        return jsonify(schema.dump(param)), 200
    except ValidationError as err:
        return jsonify({"message": "Erro validação", "errors": err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro atualização", "error": str(e)}), 500

@config_bp.route('/parametros/<int:id_param>', methods=['DELETE'])
@jwt_required()
@admin_required()
def delete_parametro(id_param):
    try:
        # Soft delete ou hard delete? Parametros podem ser críticos. Vamos hard delete se admin.
        param = Parametro.query.get_or_404(id_param)
        db.session.delete(param)
        db.session.commit()
        return jsonify({"message": "Parâmetro removido"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao deletar", "error": str(e)}), 500

# --- CRUD MODALIDADES ---
@config_bp.route('/modalidades', methods=['POST'])
@jwt_required()
@supervisor_or_admin_required()
def create_modalidade():
    json_data = request.get_json()
    schema = ModalidadeSchema()
    try:
        data = schema.load(json_data, session=db.session)
        # Serializar config se for dict (pois DB é Text)
        if isinstance(data.configuracao, (dict, list)):
            data.configuracao = json.dumps(data.configuracao)

        if Modalidade.query.filter_by(chave=data.chave).first():
            return jsonify({"message": f"Modalidade '{data.chave}' já existe."}), 409
        db.session.add(data)
        db.session.commit()
        
        # Deserializar para retorno
        if isinstance(data.configuracao, str):
            try: data.configuracao = json.loads(data.configuracao)
            except: pass
            
        return jsonify(schema.dump(data)), 201
    except ValidationError as err:
        return jsonify({"message": "Erro validação", "errors": err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao criar modalidade", "error": str(e)}), 500

@config_bp.route('/modalidades/<int:id_mod>', methods=['PUT', 'DELETE'])
@jwt_required()
@supervisor_or_admin_required()
def manage_modalidade(id_mod):
    mod = Modalidade.query.get_or_404(id_mod)
    
    if request.method == 'DELETE':
        try:
            mod.ativo = False # Soft delete
            db.session.commit()
            return jsonify({"message": "Modalidade desativada"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    # PUT
    json_data = request.get_json()
    schema = ModalidadeSchema(partial=True)
    try:
        mod = schema.load(json_data, session=db.session, instance=mod)
        
        # Serializar config se for dict
        if isinstance(mod.configuracao, (dict, list)):
            mod.configuracao = json.dumps(mod.configuracao)
            
        db.session.commit()
        
        # Deserializar para retorno
        if isinstance(mod.configuracao, str):
            try: mod.configuracao = json.loads(mod.configuracao)
            except: pass
            
        return jsonify(schema.dump(mod)), 200
    except ValidationError as err:
        return jsonify({"message": "Erro validação", "errors": err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao atualizar", "error": str(e)}), 500