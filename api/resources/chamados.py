# /api/resources/chamados.py (VERSÃƒO FINAL E CORRIGIDA)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, func
import logging
import traceback
from datetime import datetime, timedelta

from .. import db
from ..models import Chamado, Cliente, Usina, Usuario, ChamadoLog, Categoria, OrdenServico
from ..schemas.chamado_schema import ChamadoInputSchema, ChamadoOutputSchema, ChamadoLogSchema
from ..decorators import admin_required, tecnico_required, supervisor_or_admin_required
import os
from werkzeug.utils import secure_filename
from flask import send_from_directory, current_app
from ..models import Chamado, Cliente, Usina, Usuario, ChamadoLog, Categoria, OrdenServico, ChamadoAnexo, Orcamento

chamados_bp = Blueprint('chamados', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def _salvar_arquivo(file_storage, chamado_id):
    filename = secure_filename(file_storage.filename)
    # Define pasta: static/uploads/chamados/<chamado_id>
    upload_folder = os.path.join(current_app.config['CHAMADOS_UPLOAD_FOLDER'], str(chamado_id))
    
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        
    savename = f"{int(datetime.timestamp(datetime.now()))}_{filename}"
    filepath = os.path.join(upload_folder, savename)
    file_storage.save(filepath)
    
    # Caminho relativo para armazenar no banco e servir via static
    # De: api/static/uploads/chamados/1/arquivo.pdf
    # Para: uploads/chamados/1/arquivo.pdf (relativo Ã  pasta static se servirmos direto pelo Flask ou Webserver)
    # O Flask serve 'static' na url /static.
    # Vamos guardar o caminho relativo Ã  pasta 'static'.
    relative_path = f"uploads/chamados/{chamado_id}/{savename}"
    
    return filename, relative_path, os.path.getsize(filepath)

@chamados_bp.route('/<int:id_chamado>/anexos', methods=['POST'])
@jwt_required()
@tecnico_required()
def upload_anexo(id_chamado):
    """
    Faz upload de um arquivo para o chamado.
    Pode ser vinculado a um comentÃ¡rio se 'id_log' for passado.
    """
    import mimetypes
    
    if 'file' not in request.files:
        return jsonify({"message": "Nenhum arquivo enviado"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "Nenhum arquivo selecionado"}), 400
        
    if file and allowed_file(file.filename):
        try:
            current_user_id = int(get_jwt_identity())
            chamado = Chamado.query.get_or_404(id_chamado)

            # Salva fÃ­sico
            nome_original, caminho_rel, tamanho = _salvar_arquivo(file, id_chamado)
            
            # Pega id_log opcional (se vier junto com um comentÃ¡rio criado antes ou simultaneamente)
            # Nota: O frontend pode criar o comentÃ¡rio primeiro e depois enviar o anexo com o ID do log.
            id_log = request.form.get('id_log', type=int) 
            
            # Se vier comentÃ¡rio junto com upload (multipart), criamos o log agora
            comentario_texto = request.form.get('comentario')
            if comentario_texto and not id_log:
                novo_log = ChamadoLog(
                    id_chamado=id_chamado,
                    id_usuario=current_user_id,
                    campo_alterado='Anexo',
                    comentario=comentario_texto,
                    tipo_log='manual'
                )
                db.session.add(novo_log)
                db.session.flush()
                id_log = novo_log.id

            anexo = ChamadoAnexo(
                id_chamado=id_chamado,
                id_usuario=current_user_id,
                id_log=id_log,
                nome_arquivo=nome_original,
                caminho_arquivo=caminho_rel,
                mime_type=mimetypes.guess_type(nome_original)[0] or 'application/octet-stream',
                tamanho_bytes=tamanho
            )
            
            db.session.add(anexo)
            db.session.commit()
            
            return jsonify({
                "message": "Upload realizado com sucesso",
                "anexo": {
                    "id": anexo.id_anexo,
                    "nome": anexo.nome_arquivo,
                    "url": f"/static/{anexo.caminho_arquivo}", # URL pÃºblica
                    "tamanho": anexo.tamanho_bytes,
                    "id_log": anexo.id_log
                }
            }), 201

        except Exception as e:
            db.session.rollback()
            logging.error(f"ERRO UPLOAD ANEXO: {e}\n{traceback.format_exc()}")
            return jsonify({"message": "Erro ao salvar anexo", "error": str(e)}), 500
    
    return jsonify({"message": "Tipo de arquivo nÃ£o permitido"}), 400

@chamados_bp.route('/<int:id_chamado>/anexos', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_anexos(id_chamado):
    """Lista todos os anexos de um chamado."""
    anexos = ChamadoAnexo.query.filter_by(id_chamado=id_chamado).order_by(ChamadoAnexo.data_upload.desc()).all()
    
    results = []
    for a in anexos:
        results.append({
            "id": a.id_anexo,
            "nome": a.nome_arquivo,
            "url": f"/static/{a.caminho_arquivo}",
            "tipo": a.mime_type,
            "tamanho": a.tamanho_bytes,
            "data": a.data_upload.isoformat(),
            "usuario": a.usuario.nome_usuario if a.usuario else "Sistema",
            "id_log": a.id_log
        })
        
    return jsonify(results), 200

@chamados_bp.route('/anexos/<int:id_anexo>', methods=['DELETE'])
@jwt_required()
@tecnico_required()
def deletar_anexo(id_anexo):
    """Deleta um anexo."""
    anexo = ChamadoAnexo.query.get_or_404(id_anexo)
    
    # Opcional: Verificar se usuÃ¡rio Ã© dono ou admin
    # current_user = get_jwt_identity()
    
    try:
        # Remove arquivo fÃ­sico
        full_path = os.path.join(current_app.config['basedir'], 'api', 'static', anexo.caminho_arquivo)
        # O caminho salvo Ã© relativo a 'api/static', mas config['UPLOAD_FOLDER'] Ã© absoluto.
        # Precisamos reconstruir o caminho absoluto corretamente.
        # Caminho salvo: uploads/chamados/ID/file.ext
        # Base static: api/static
        # Absolute: basedir/api/static/uploads...
        
        # CorreÃ§Ã£o da lÃ³gica de path:
        # savename no _salvar_arquivo Ã© relativo Ã  pasta uploads.
        # caminho_arquivo no banco: uploads/chamados/...
        # Vamos usar o basedir configurado app
        
        abs_path = os.path.join(current_app.root_path, 'static', anexo.caminho_arquivo)
        
        if os.path.exists(abs_path):
            os.remove(abs_path)
            
        db.session.delete(anexo)
        db.session.commit()
        
        return jsonify({"message": "Anexo deletado com sucesso"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao deletar anexo", "error": str(e)}), 500


@chamados_bp.route('/stats', methods=['GET'])
@jwt_required()
@tecnico_required()
def get_chamados_stats():
    """Retorna estatÃ­sticas para o dashboard de chamados."""
    try:
        agora = datetime.now()
        sete_dias_atras = agora - timedelta(days=7)
        trinta_dias_atras = agora - timedelta(days=30)
        
        categoria_filter = request.args.get('categoria')

        # --- ESTATÃSTICAS GLOBAIS (SNAPSHOT DO BACKLOG) ---
        
        # 1. Total por Status (Todos os chamados ativos)
        status_query = db.session.query(
            Chamado.status, func.count(Chamado.id_chamado)
        ).filter(Chamado.is_active == True)

        if categoria_filter:
            status_query = status_query.filter(Chamado.categoria == categoria_filter)
        
        status_totals = dict(status_query.group_by(Chamado.status).all())

        # 2. Total em aberto por Categoria (Ativos)
        # Nota: Normalmente dashboards mostram "Backlog por Categoria" (exclui concluÃ­dos)
        # Se quiser "Total por Categoria" (incluindo fechados), remover o filtro de notin_
        # Vamos assumir Backlog Ativo aqui.
        abertos_cat_query = db.session.query(
            Chamado.categoria, func.count(Chamado.id_chamado)
        ).filter(
            Chamado.status.notin_(['Resolvido', 'Concluido', 'Cancelado', 'Arquivada']),
            Chamado.is_active == True
        )
        if categoria_filter:
             abertos_cat_query = abertos_cat_query.filter(Chamado.categoria == categoria_filter)
             
        abertos_por_categoria = dict(abertos_cat_query.group_by(Chamado.categoria).all())

        # 3. Total Geral Registrado (Ativos no sistema)
        total_query = Chamado.query.filter(Chamado.is_active == True)
        if categoria_filter:
            total_query = total_query.filter(Chamado.categoria == categoria_filter)
        total_registrados = total_query.count()


        # --- ESTATÃSTICAS PERIÃ“DICAS (ÃšLTIMOS 30 DIAS) ---

        # 4. Total abertos na Ãºltima semana (Agora 30 dias para consistÃªncia com nome da var)
        # Nome da variÃ¡vel sugere semana, mas cÃ³digo original usava 30 dias. Mantendo 30 dias como "PerÃ­odo Recente".
        total_abertos_semana = Chamado.query.filter(
            Chamado.data_criacao >= trinta_dias_atras,
            Chamado.is_active == True
        ).count()
        
        # 5. Total resolvidos no perÃ­odo
        total_resolvidos_semana = ChamadoLog.query.filter(
            ChamadoLog.campo_alterado == 'Status',
            ChamadoLog.valor_novo.in_(['Resolvido', 'Concluido']),
            ChamadoLog.timestamp >= trinta_dias_atras
        ).count()

        # 6. GrÃ¡fico de pico de atividade (Logs por dia)
        logs_periodo = ChamadoLog.query.filter(ChamadoLog.timestamp >= trinta_dias_atras).all()
        pico_atividade = {}
        for log in logs_periodo:
            dia = log.timestamp.strftime('%Y-%m-%d')
            pico_atividade[dia] = pico_atividade.get(dia, 0) + 1
            
        # 7. Chamados precisando de atenÃ§Ã£o (Sem atividade hÃ¡ mais de 7 dias)
        # Usa group_by e having para filtrar
        atencao_query = db.session.query(Chamado).outerjoin(ChamadoLog)\
            .filter(
                Chamado.status.notin_(['Resolvido', 'Concluido', 'Cancelada', 'Arquivada']),
                Chamado.is_active == True
            )\
            .group_by(Chamado.id_chamado)\
            .having(func.max(ChamadoLog.timestamp) < sete_dias_atras)
            
        if categoria_filter:
            atencao_query = atencao_query.filter(Chamado.categoria == categoria_filter)
            
        atencao_necessaria_items = atencao_query.order_by(Chamado.data_criacao.asc()).limit(10).all()
        atencao_necessaria = ChamadoOutputSchema(many=True).dump(atencao_necessaria_items)
        
        # 8. Timeline recente
        timeline_logs = ChamadoLog.query.order_by(ChamadoLog.timestamp.desc()).limit(20).all()
        timeline = ChamadoLogSchema(many=True).dump(timeline_logs)

        logging.info(f"STATS REFACTORED: totals={status_totals}")

        return jsonify({
            "total_abertos_semana": total_abertos_semana,
            "total_resolvidos_semana": total_resolvidos_semana,
            "abertos_por_categoria": abertos_por_categoria,
            "total_registrados": total_registrados,
            "pico_atividade": pico_atividade,
            "atencao_necessaria": atencao_necessaria,
            "timeline": timeline,
            "status_totals": status_totals
        }), 200
        
    except Exception as e:
        logging.error(f"ERRO AO GERAR ESTATISTICAS: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro ao gerar estatÃ­sticas", "error": str(e)}), 500


@chamados_bp.route('', methods=['POST'])
@jwt_required()
@tecnico_required()
def criar_chamado():
    """Cria um novo chamado."""
    try:
        id_usuario_responsavel = int(get_jwt_identity())
    except (ValueError, TypeError):
        return jsonify({"message": "Token de usuÃ¡rio invÃ¡lido"}), 422
        
    json_data = request.get_json()

    schema = ChamadoInputSchema()
    try:
        data = schema.load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validaÃ§Ã£o", "errors": err.messages}), 400

    if not Cliente.query.get(data['id_cliente']):
        return jsonify({"message": "Cliente nÃ£o encontrado"}), 404
    if not Usina.query.get(data['id_usina']):
        return jsonify({"message": "Usina nÃ£o encontrada"}), 404

    novo_chamado = Chamado(
        id_usuario_responsavel=id_usuario_responsavel,
        id_cliente=data['id_cliente'],
        id_usina=data['id_usina'],
        titulo=data['titulo'],
        descricao=data['descricao'],
        categoria=data['categoria'],
        prioridade=data['prioridade']
        # O status 'Aberto' e 'is_active=True' sÃ£o definidos por padrÃ£o no modelo
    )

    try:
        db.session.add(novo_chamado)
        db.session.flush() # Faz o flush para obter o novo ID
        # --- ADICIONA O LOG DE CRIAÃ‡ÃƒO ---
        log_criacao = ChamadoLog(
            id_chamado = novo_chamado.id_chamado,
            id_usuario = id_usuario_responsavel,
            campo_alterado = "CriaÃ§Ã£o",
            valor_novo = novo_chamado.titulo
        )
        db.session.add(log_criacao)
        db.session.commit()
        return jsonify(ChamadoOutputSchema().dump(novo_chamado)), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"ERRO AO CRIAR CHAMADO: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro ao criar o chamado", "error": str(e)}), 500


@chamados_bp.route('', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_chamados():
    """
    Lista chamados com suporte a filtros e paginaÃ§Ã£o.
    
    Query Parameters:
    - cidade: filtro por cidade da usina (case-insensitive)
    - status: filtro por status do chamado
    - prioridade: filtro por prioridade
    - categoria: filtro por categoria
    - responsavel_id: filtro por ID do usuÃ¡rio responsÃ¡vel
    - data_inicio: data inicial (formato: YYYY-MM-DD)
    - data_fim: data final (formato: YYYY-MM-DD)
    - limit: nÃºmero de itens por pÃ¡gina (padrÃ£o: 10)
    - offset: deslocamento para paginaÃ§Ã£o (padrÃ£o: 0)
    """
    try:
        # ParÃ¢metros de paginaÃ§Ã£o
        limit = request.args.get('limit', 10, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        logging.info(f"LISTAR_CHAMADOS REQUEST ARGS: {request.args}")
        
        # Inicia a query base - apenas chamados ativos
        query = Chamado.query.filter(Chamado.is_active == True)

        # --- FILTRO GERAL (Search Bar) ---
        search_term = request.args.get('search', type=str) or request.args.get('q', type=str)
        if search_term:
            # Garante joins necessÃ¡rios para a busca
            query = query.join(Usina).join(Cliente)
            
            search_filter = or_(
                Chamado.titulo.ilike(f'%{search_term}%'),
                func.cast(Chamado.id_chamado, db.String).ilike(f'%{search_term}%'),
                Usina.nome_usina.ilike(f'%{search_term}%'),
                Cliente.nome.ilike(f'%{search_term}%')
            )
            query = query.filter(search_filter)
        
        # Filtro por cidade (busca na tabela Usina)
        cidade = request.args.get('cidade', type=str)
        if cidade:
            query = query.join(Usina).filter(Usina.cidade.ilike(f'%{cidade}%'))

        # Filtro por nome da usina
        usina_nome = request.args.get('usina', type=str)
        if usina_nome:
            # Verifica se jÃ¡ houve join com Usina (se cidade foi filtrada)
            if not cidade:
                query = query.join(Usina)
            query = query.filter(Usina.nome_usina.ilike(f'%{usina_nome}%'))

        # Filtro por status
        status = request.args.get('status', type=str)
        if status:
            query = query.filter(Chamado.status == status)

        # Filtro por prioridade
        prioridade = request.args.get('prioridade', type=str)
        if prioridade:
            query = query.filter(Chamado.prioridade == prioridade)
        
        # Filtro por categoria
        categoria = request.args.get('categoria', type=str)
        if categoria:
            query = query.filter(Chamado.categoria == categoria)
        
        # Filtro por responsÃ¡vel
        responsavel_id = request.args.get('responsavel_id', type=int)
        if responsavel_id:
            query = query.filter(Chamado.id_usuario_responsavel == responsavel_id)

        # --- FILTROS DE EXCEÃ‡ÃƒO (_not) ---
        
        status_not = request.args.get('status_not', type=str)
        if status_not:
            query = query.filter(Chamado.status != status_not)

        prioridade_not = request.args.get('prioridade_not', type=str)
        if prioridade_not:
            query = query.filter(Chamado.prioridade != prioridade_not)

        categoria_not = request.args.get('categoria_not', type=str)
        if categoria_not:
            query = query.filter(Chamado.categoria != categoria_not)

        responsavel_id_not = request.args.get('responsavel_id_not', type=int)
        if responsavel_id_not:
            query = query.filter(Chamado.id_usuario_responsavel != responsavel_id_not)
        
        # Filtro por data de criaÃ§Ã£o
        data_inicio = request.args.get('data_inicio', type=str)
        data_fim = request.args.get('data_fim', type=str)
        
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(Chamado.data_criacao >= data_inicio_obj)
            except ValueError:
                return jsonify({"message": "Formato de data_inicio invÃ¡lido. Use YYYY-MM-DD"}), 400
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
                # Adiciona 23:59:59 para incluir todo o dia
                data_fim_obj = data_fim_obj + timedelta(days=1) - timedelta(seconds=1)
                query = query.filter(Chamado.data_criacao <= data_fim_obj)
            except ValueError:
                return jsonify({"message": "Formato de data_fim invÃ¡lido. Use YYYY-MM-DD"}), 400
        
        # Conta o total antes de aplicar paginaÃ§Ã£o
        total = query.count()
        
        # Aplica ordenaÃ§Ã£o e paginaÃ§Ã£o
        query_paginada = query.order_by(Chamado.data_criacao.desc()).limit(limit).offset(offset)
        logging.info(f"QUERY SQL: {str(query_paginada.statement.compile(compile_kwargs={'literal_binds': True}))}")
        chamados = query_paginada.all()
        
        # Retorna resposta paginada
        # Retorna resposta paginada
        output_data = ChamadoOutputSchema(many=True).dump(chamados)
        
        # Injeta status de lembrete
        for i, c in enumerate(chamados):
            # Garante que c.lembretes existe (se relacionamento definido)
            if hasattr(c, 'lembretes'):
                pending = any(l.status == 'pendente' for l in c.lembretes)
                output_data[i]['has_lembrete_pendente'] = pending
            else:
                output_data[i]['has_lembrete_pendente'] = False

        return jsonify({
            "results": output_data,
            "total": total
        }), 200
        
    except Exception as e:
        logging.error(f"ERRO AO LISTAR CHAMADOS: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro ao listar chamados", "error": str(e)}), 500


@chamados_bp.route('/<int:id_chamado>', methods=['GET'])
@jwt_required()
@tecnico_required()
def detalhar_chamado(id_chamado):
    """Retorna os detalhes de um chamado especÃ­fico (ativo ou nÃ£o)."""
    chamado = Chamado.query.get_or_404(id_chamado)
    return jsonify(ChamadoOutputSchema().dump(chamado))


@chamados_bp.route('/<int:id_chamado>', methods=['PUT'])
@jwt_required()
@tecnico_required()
def atualizar_chamado(id_chamado):
    """
    Atualiza um chamado existente e cria um log de auditoria para cada campo alterado.
    Regra de negocio:
    - Ao mudar para status "Agendando Visita", cria automaticamente uma OS vinculada (se nao existir aberta).
    """
    chamado = Chamado.query.get_or_404(id_chamado)
    json_data = request.get_json()

    schema = ChamadoInputSchema(partial=True)
    try:
        data = schema.load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validacao", "errors": err.messages}), 400

    try:
        current_user_id = int(get_jwt_identity())
        logs_to_add = []
        id_ordem_servico_created = None

        novo_status = data.get('status')

        # 0) Validacao dinamica de status + automacao de Orcamento
        if novo_status is not None:
            status_valido = Categoria.query.filter_by(
                tipo='status_chamado',
                nome=novo_status,
                is_active=True
            ).first()

            if not status_valido:
                return jsonify({"message": f"Status '{novo_status}' invalido ou inativo."}), 400

            if novo_status == 'Montando Orçamento':
                orcamento_existente = Orcamento.query.filter_by(id_chamado=id_chamado).first()
                if not orcamento_existente:
                    logging.info(f"Auto-creating Budget for Chamado {id_chamado}")

                    modalidade_inicial = 'assistencia_paga'
                    descricao_extra = ""
                    try:
                        import json
                        usina_obj = chamado.usina
                        if usina_obj and usina_obj.solarz_payload:
                            payload_data = json.loads(usina_obj.solarz_payload) if isinstance(usina_obj.solarz_payload, str) else usina_obj.solarz_payload
                            inst_date_str = payload_data.get('installationDate')
                            if inst_date_str:
                                inst_date = datetime.fromisoformat(inst_date_str.replace('Z', ''))
                                one_year_ago = datetime.now() - timedelta(days=365)
                                if inst_date > one_year_ago:
                                    modalidade_inicial = 'garantia_instalacao'
                                    descricao_extra = " (Garantia de Instalacao - Menos de 1 ano)"
                                else:
                                    descricao_extra = "\n\nUsina sem garantia, mais de um ano (tempo de instalacao)."
                            else:
                                descricao_extra = "\n\nData de instalacao nao encontrada no cadastro SolarZ."
                        else:
                            descricao_extra = "\n\nUsina sem dados SolarZ para verificacao de garantia."
                    except Exception as e_garantia:
                        logging.error(f"Erro ao verificar garantia de instalacao: {e_garantia}")
                        descricao_extra = "\n\n(Erro verif. garantia)"

                    novo_orc = Orcamento(
                        id_chamado=id_chamado,
                        id_cliente=chamado.id_cliente,
                        id_usina=chamado.id_usina,
                        id_usuario_responsavel=current_user_id,
                        status='pendente',
                        descricao_servico=f"Orcamento referente ao Chamado #{chamado.titulo}.{descricao_extra}",
                        data_validade=datetime.now() + timedelta(days=15),
                        modalidade=modalidade_inicial
                    )
                    db.session.add(novo_orc)
                    db.session.flush()

                    logs_to_add.append(ChamadoLog(
                        id_chamado=id_chamado,
                        id_usuario=current_user_id,
                        campo_alterado='Sistema',
                        valor_novo=f"Orcamento #{novo_orc.id_orcamento} criado automaticamente ({modalidade_inicial}).",
                        tipo_log='automatico'
                    ))

        # 1) Responsavel
        if 'id_usuario_responsavel' in data:
            new_resp_id = int(data['id_usuario_responsavel'])
            old_resp_id = chamado.id_usuario_responsavel

            if new_resp_id != old_resp_id:
                old_user = Usuario.query.get(old_resp_id)
                new_user = Usuario.query.get(new_resp_id)
                old_name = old_user.nome_usuario if old_user else f"ID {old_resp_id}"
                new_name = new_user.nome_usuario if new_user else f"ID {new_resp_id}"

                chamado.id_usuario_responsavel = new_resp_id
                logs_to_add.append(ChamadoLog(
                    id_chamado=id_chamado,
                    id_usuario=current_user_id,
                    campo_alterado='Responsavel',
                    valor_antigo=old_name,
                    valor_novo=new_name,
                    tipo_log='automatico'
                ))

        # 2) Campos genericos
        for key, new_value in data.items():
            if key in ['id_usuario_responsavel', 'comentario']:
                continue

            if hasattr(chamado, key):
                old_value = getattr(chamado, key)
                if str(old_value) != str(new_value):
                    setattr(chamado, key, new_value)
                    logs_to_add.append(ChamadoLog(
                        id_chamado=id_chamado,
                        id_usuario=current_user_id,
                        campo_alterado=key.capitalize(),
                        valor_antigo=str(old_value),
                        valor_novo=str(new_value),
                        tipo_log='automatico'
                    ))

        # 3) Comentario manual
        comentario_texto = data.get('comentario')
        if comentario_texto:
            logs_to_add.append(ChamadoLog(
                id_chamado=id_chamado,
                id_usuario=current_user_id,
                campo_alterado='Comentario',
                comentario=comentario_texto,
                tipo_log='manual'
            ))

        # 4) Automacao: ao entrar em "Agendando Visita", garantir OS aberta vinculada
        if chamado.status == 'Agendando Visita':
            existing_os = (
                OrdenServico.query
                .filter_by(id_chamado=chamado.id_chamado)
                .order_by(OrdenServico.id_orden_servico.desc())
                .first()
            )

            if not existing_os or existing_os.status in ['Concluida', 'Resolvida', 'Cancelada', 'Arquivada']:
                nova_os = OrdenServico(
                    id_chamado=chamado.id_chamado,
                    id_cliente=chamado.id_cliente,
                    id_usina=chamado.id_usina,
                    id_usuario_responsavel=chamado.id_usuario_responsavel,
                    status='Aberta',
                    id_orcamento=None
                )
                db.session.add(nova_os)
                db.session.flush()
                id_ordem_servico_created = nova_os.id_orden_servico

                logs_to_add.append(ChamadoLog(
                    id_chamado=chamado.id_chamado,
                    id_usuario=current_user_id,
                    campo_alterado='Sistema',
                    valor_novo=f"OS #{nova_os.id_orden_servico} criada automaticamente ao mover chamado para Agendando Visita.",
                    tipo_log='automatico'
                ))

        if db.session.is_modified(chamado) or logs_to_add:
            if logs_to_add:
                db.session.add_all(logs_to_add)
            db.session.commit()

    except Exception as e:
        db.session.rollback()
        logging.error(f"ERRO AO ATUALIZAR CHAMADO ID {id_chamado}: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro ao atualizar o chamado", "error": str(e)}), 500

    response_data = ChamadoOutputSchema().dump(chamado)
    if id_ordem_servico_created:
        response_data['id_ordem_servico_novo'] = id_ordem_servico_created
    else:
        existing_os = (
            OrdenServico.query
            .filter_by(id_chamado=chamado.id_chamado)
            .order_by(OrdenServico.id_orden_servico.desc())
            .first()
        )
        if existing_os:
            response_data['id_ordem_servico'] = existing_os.id_orden_servico

    return jsonify(response_data)

@chamados_bp.route('/<int:id_chamado>', methods=['DELETE'])
@jwt_required()
@tecnico_required()
def deletar_chamado(id_chamado):
    """Arquiva um chamado (Soft Delete)."""
    chamado = Chamado.query.get_or_404(id_chamado)
    current_user_id = int(get_jwt_identity())
    try:
        # --- ADICIONA O LOG DE ARQUIVAMENTO ---
        log_arquivo = ChamadoLog(
            id_chamado = chamado.id_chamado,
            id_usuario = current_user_id,
            campo_alterado = "Status",
            valor_antigo = chamado.status,
            valor_novo = "Arquivado"
        )
        db.session.add(log_arquivo)
        chamado.is_active = False
        chamado.status = 'Arquivado'
        db.session.commit()
        return jsonify({"message": f"Chamado ID {id_chamado} arquivado com sucesso."}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"ERRO AO ARQUIVAR CHAMADO ID {id_chamado}: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro ao arquivar o chamado", "error": str(e)}), 500


@chamados_bp.route('/<int:id_chamado>/restore', methods=['PUT'])
@jwt_required()
@supervisor_or_admin_required()
def restaurar_chamado(id_chamado):
    """Restaura um chamado arquivado."""
    chamado = Chamado.query.get_or_404(id_chamado)
    if not chamado.is_active:
        chamado.is_active = True
        chamado.status = 'Aberto'
        db.session.commit()
        return jsonify(ChamadoOutputSchema().dump(chamado)), 200
    return jsonify({"message": "Chamado jÃ¡ estÃ¡ ativo."}), 400


@chamados_bp.route('/<int:id_chamado>/logs', methods=['GET'])
@jwt_required()
@tecnico_required()
def get_chamado_logs(id_chamado):
    """Retorna o histÃ³rico de logs de um chamado especÃ­fico."""
    chamado = Chamado.query.get_or_404(id_chamado)
    # 'lazy=dynamic' no modelo nos permite fazer 'order_by' aqui
    logs = chamado.logs.order_by(ChamadoLog.timestamp.desc()).all()
    return jsonify(ChamadoLogSchema(many=True).dump(logs)), 200


@chamados_bp.route('/<int:id_chamado>/comentarios', methods=['POST'])
@jwt_required()
@tecnico_required()
def adicionar_comentario(id_chamado):
    """Adiciona um comentÃ¡rio manual a um chamado."""
    current_user_id = int(get_jwt_identity())
    json_data = request.get_json()
    comentario_texto = json_data.get('comentario')

    if not comentario_texto:
        return jsonify({"message": "ComentÃ¡rio nÃ£o pode ser vazio"}), 400

    try:
        # Busca o chamado para atualizar a data de modificaÃ§Ã£o
        chamado = Chamado.query.get_or_404(id_chamado)
        
        novo_log = ChamadoLog(
            id_chamado=id_chamado,
            id_usuario=current_user_id,
            campo_alterado='ComentÃ¡rio',
            comentario=comentario_texto,
            tipo_log='manual'
        )
        db.session.add(novo_log)
        
        # ForÃ§a atualizaÃ§Ã£o da data do chamado
        chamado.data_atualizacao = func.now()
        
        db.session.commit()
        return jsonify(ChamadoLogSchema().dump(novo_log)), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"ERRO AO ADICIONAR COMENTÃRIO: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro ao salvar o comentÃ¡rio", "error": str(e)}), 500


@chamados_bp.route('/ativos', methods=['GET'])
@jwt_required()
@tecnico_required()
def listar_chamados_ativos():
    """
    Retorna uma lista de todos os chamados que estÃ£o 'Abertos' ou 'Em Andamento'
    para preencher seletores no frontend.
    """
    try:
        chamados_ativos = Chamado.query.filter(
            Chamado.is_active == True,
            or_(
                Chamado.status == 'Aberto',
                Chamado.status == 'Em Andamento'
            )
        ).order_by(Chamado.data_criacao.desc()).all()

        # Retorna todos os dados, pois o frontend precisarÃ¡ do cliente/usina
        return jsonify(ChamadoOutputSchema(many=True).dump(chamados_ativos)), 200
    except Exception as e:
        return jsonify({"message": "Erro ao buscar chamados ativos", "error": str(e)}), 500


@chamados_bp.route('/comentarios/<int:id_log>', methods=['PUT'])
@jwt_required()
@tecnico_required()
def editar_comentario(id_log):
    """Edita um comentÃ¡rio existente."""
    current_user_id = int(get_jwt_identity())
    
    log = ChamadoLog.query.get_or_404(id_log)
    
    # PermissÃ£o: Apenas o autor ou admin
    if log.id_usuario != current_user_id:
        user = Usuario.query.get(current_user_id)
        if user.tipo_usuario != 'admin':
             return jsonify({"message": "Sem permissÃ£o para editar este comentÃ¡rio"}), 403

    json_data = request.get_json()
    novo_texto = json_data.get('comentario')

    if not novo_texto:
        return jsonify({"message": "ComentÃ¡rio nÃ£o pode ser vazio"}), 400

    log.comentario = novo_texto
    log.campo_alterado = 'ComentÃ¡rio Editado'
    db.session.commit()
    return jsonify(ChamadoLogSchema().dump(log)), 200


@chamados_bp.route('/comentarios/<int:id_log>', methods=['DELETE'])
@jwt_required()
@tecnico_required()
def deletar_comentario(id_log):
    """Deleta um comentÃ¡rio existente."""
    current_user_id = int(get_jwt_identity())
    log = ChamadoLog.query.get_or_404(id_log)

    # PermissÃ£o: Apenas o autor ou admin
    if log.id_usuario != current_user_id:
        user = Usuario.query.get(current_user_id)
        if user.tipo_usuario != 'admin':
             return jsonify({"message": "Sem permissÃ£o para deletar este comentÃ¡rio"}), 403

    try:
        db.session.delete(log)
        db.session.commit()
        return jsonify({"message": "ComentÃ¡rio deletado com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao deletar comentÃ¡rio", "error": str(e)}), 500
