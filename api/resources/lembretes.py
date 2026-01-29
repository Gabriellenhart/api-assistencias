from flask import Blueprint, request, jsonify
from ..models import db, ChamadoLembrete, Chamado
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime
import logging

bp = Blueprint('lembretes', __name__, url_prefix='/lembretes')

@bp.route('/<int:id_chamado>', methods=['POST'])
@jwt_required()
def criar_lembrete(id_chamado):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Dados não fornecidos'}), 400
            
        titulo = data.get('titulo')
        data_lembrete_str = data.get('data')
        
        if not titulo or not data_lembrete_str:
             return jsonify({'message': 'Título e Data são obrigatórios'}), 400
             
        try:
            # Tenta converter ISO ou Date string
            data_lembrete = datetime.fromisoformat(data_lembrete_str.replace('Z', '+00:00'))
        except ValueError:
             return jsonify({'message': 'Formato de data inválido'}), 400

        # Verifica se chamado existe
        chamado = Chamado.query.get(id_chamado)
        if not chamado:
             return jsonify({'message': 'Chamado não encontrado'}), 404

        id_chamado_log = data.get('id_comentario') # Recebe o ID do comentário (log)

        novo_lembrete = ChamadoLembrete(
            id_chamado=id_chamado,
            id_usuario_criador=current_user.id_usuario,
            titulo=titulo,
            data_lembrete=data_lembrete,
            status='pendente',
            id_chamado_log=id_chamado_log
        )
        
        db.session.add(novo_lembrete)
        db.session.commit()
        
        return jsonify({'message': 'Lembrete criado com sucesso', 'id': novo_lembrete.id_lembrete}), 201
        
    except Exception as e:
        logging.error(f"Erro ao criar lembrete: {e}")
        return jsonify({'message': 'Erro interno ao criar lembrete'}), 500

@bp.route('/pendentes', methods=['GET'])
@jwt_required()
def listar_pendentes():
    try:
        from sqlalchemy import case, asc
        
        # Ordem de prioridade personalizada
        prioridade_order = case(
            (Chamado.prioridade == 'Urgente', 1),
            (Chamado.prioridade == 'Alta', 2),
            (Chamado.prioridade == 'Média', 3),
            (Chamado.prioridade == 'Baixa', 4),
            else_=5
        )

        lembretes = ChamadoLembrete.query\
            .join(Chamado)\
            .filter(ChamadoLembrete.status == 'pendente')\
            .order_by(
                prioridade_order,              # 1º Critério: Prioridade (Descrescente tecnicamente, mas 1 é maior urgência)
                asc(ChamadoLembrete.data_lembrete) # 2º Critério: Data de vencimento (Mais antigo primeiro)
            ).all()

        results = []
        for l in lembretes:
            results.append({
                'id_lembrete': l.id_lembrete,
                'titulo': l.titulo,
                'data_lembrete': l.data_lembrete.isoformat() if l.data_lembrete else None,
                'status': l.status,
                'chamado': {
                    'id_chamado': l.chamado.id_chamado,
                    'titulo': l.chamado.titulo,
                    'prioridade': l.chamado.prioridade,
                    'cliente_nome': l.chamado.cliente.nome if l.chamado.cliente else 'N/A'
                }
            })

        return jsonify(results), 200

    except Exception as e:
        logging.error(f"Erro ao listar lembretes pendentes: {e}")
        return jsonify({'message': 'Erro interno ao listar lembretes'}), 500

@bp.route('/<int:id_lembrete>/concluir', methods=['PUT'])
@jwt_required()
def concluir_lembrete(id_lembrete):
    lembrete = ChamadoLembrete.query.get(id_lembrete)
    if not lembrete:
         return jsonify({'message': 'Lembrete não encontrado'}), 404
         
    if lembrete.status == 'concluido':
        lembrete.status = 'pendente'
        lembrete.data_conclusao = None
    else:
        lembrete.status = 'concluido'
        lembrete.data_conclusao = datetime.now()
    
    db.session.commit()
    return jsonify({'message': f'Lembrete alterado para {lembrete.status}'}), 200
