from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import case, func, or_
import logging
import traceback
from datetime import datetime, date

from .. import db
from ..models import (
    Chamado, Usina, Cliente, Usuario, OrdenServico, ConfiguracaoOperacional,
    PlanejamentoSemana, PlanejamentoDia,
)
from ..services.capacity_calculation_service import CapacityCalculationService
from ..services.rescheduling_service import ReschedulingService
from ..services.route_optimization_service import RouteOptimizationService
from ..services.time_estimation_service import TimeEstimationService
from ..services.scheduling_engine import SchedulingEngine


planejamento_bp = Blueprint('planejamento', __name__)

@planejamento_bp.route('', methods=['GET'])
@jwt_required()
def listar_planejamento():
    """
    Retorna dados para o Menu de Planejamento.
    Apenas chamados com status 'Agendando Visita'.
    Retorna objetos formatados para Lista, Mapa e Agenda.
    """
    try:
        # 1. Analisar filtros
        cidade = request.args.get('cidade')
        prioridade = request.args.get('prioridade')
        data_str = request.args.get('data') # YYYY-MM-DD

        # 2. Buscar chamados no status correto
        # Joined load strategies might be good, but explicit joins for filtering work well
        query = Chamado.query.join(Usina).join(Cliente).outerjoin(Usuario, Chamado.id_usuario_responsavel == Usuario.id_usuario).filter(Chamado.status == 'Agendando Visita')

        # 3. Aplicar filtros
        if cidade:
            query = query.filter(Usina.cidade.ilike(f'%{cidade}%'))
        
        if prioridade:
            query = query.filter(Chamado.prioridade.ilike(prioridade))

        if data_str:
            try:
                data_filter = datetime.strptime(data_str, '%Y-%m-%d').date()
                # Cast DateTime to Date for comparison
                query = query.filter(func.date(Chamado.data_agendamento) == data_filter)
            except ValueError:
                 return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD"}), 400

        # Ordenação: Prioridade (Alta > Média > Baixa) e Data Agendamento
        priority_order = case(
            (Chamado.prioridade == 'Alta', 1),
            (Chamado.prioridade == 'Média', 2),
            (Chamado.prioridade == 'Baixa', 3),
            else_=4
        )

        # Ordena por prioridade ASC (1=Alta), depois data_agendamento ASC (mais próxima)
        query = query.order_by(priority_order, Chamado.data_agendamento.asc())

        chamados = query.all()


        # 4. Montar listagens e objetos
        lista_chamados = []
        mapa_usinas = []
        agenda_eventos = []

        # Optimization: Fetch all related OSs in one query
        chamado_ids = [c.id_chamado for c in chamados]
        map_os = {}
        if chamado_ids:
            # Check for any OS linked to these IDs
            oss = OrdenServico.query.filter(OrdenServico.id_chamado.in_(chamado_ids)).all()
            for os_obj in oss:
                map_os[os_obj.id_chamado] = os_obj.id_orden_servico


        # New: Listar Técnicos
        tecnicos_query = Usuario.query.filter(or_(Usuario.nivel == 'tecnico', Usuario.nivel == 'supervisor')).all()
        lista_tecnicos = []
        for t in tecnicos_query:
            lista_tecnicos.append({
                "id": t.id_usuario,
                "nome": t.nome_usuario,
                "avatar": t.avatar_filename
            })

        for c in chamados:
            # Formata datas
            data_abertura_fmt = c.data_criacao.strftime('%Y-%m-%d') if c.data_criacao else None
            data_agendamento_fmt = c.data_agendamento.strftime('%Y-%m-%d') if c.data_agendamento else None
            horario_fmt = c.data_agendamento.strftime('%H:%M') if c.data_agendamento else None

            tecnico_nome = c.usuario.nome_usuario if c.usuario else None
            endereco_completo = f"{c.usina.logradouro}, {c.usina.cidade} - {c.usina.estado}"
            
            # Lookup OS ID
            id_os = map_os.get(c.id_chamado)

            # --- Lista de Chamados (Backlog - Apenas se NÃO tiver agendamento) ---
            if not data_agendamento_fmt:
                lista_chamados.append({
                    "id": str(c.id_chamado),
                    "cliente": c.cliente.nome,
                    "endereco": endereco_completo,
                    "cidade": c.usina.cidade,
                    "prioridade": c.prioridade,
                    "data_abertura": data_abertura_fmt,
                    "data_agendamento": data_agendamento_fmt,
                    "status": c.status,
                    "descricao": c.descricao,
                    # Extra fields for Card Lateral (can be reused from list item logic)
                    "contato_cliente": c.cliente.contato_telefone or c.cliente.contato_email,
                    "tecnico_responsavel": tecnico_nome,
                    "id_ordem_servico": id_os
                })

            # --- Mapa ---
            # Assume latitude/longitude are stored in Usina
            # Check if lat/long are valid numbers
            try:
                lat = float(c.usina.latitude) if c.usina.latitude else None
                lng = float(c.usina.longitude) if c.usina.longitude else None
                
                if lat is not None and lng is not None:
                    mapa_usinas.append({
                        "id": str(c.id_chamado), # Usando ID do chamado para facilitar link
                        "latitude": lat,
                        "longitude": lng,
                        "status": c.status,
                        "cliente": c.cliente.nome,
                        "cidade": c.usina.cidade,
                        "id_ordem_servico": id_os
                    })
            except (ValueError, TypeError):
                pass # Skip invalid coordinates

            # --- Agenda ---
            if data_agendamento_fmt:
                agenda_eventos.append({
                    "id": str(c.id_chamado),
                    "cliente": c.cliente.nome,
                    "data_agendamento": data_agendamento_fmt,
                    "horario": horario_fmt,
                    "tecnico_responsavel": tecnico_nome,
                    "id_tecnico": c.id_usuario_responsavel,
                    # Extra fields for Side Card details
                    "endereco": endereco_completo,
                    "cidade": c.usina.cidade,
                    "prioridade": c.prioridade,
                    "status": c.status,
                    "descricao": c.descricao,
                    "contato_cliente": c.cliente.contato_telefone or c.cliente.contato_email,
                    "id_ordem_servico": id_os
                })

        # --- KPIs & Oportunidades (Dashboard) ---
        # Calcular KPIs
        hoje = datetime.now().date()
        
        # 1. Visitas Hoje (chamados agendados para HOJE)
        # Nota: Idealmente seria uma query separada para performance, mas com poucos dados Python resolve.
        # Se escalar, mover para count() no banco.
        visitas_hoje = sum(1 for c in chamados if c.data_agendamento and c.data_agendamento.date() == hoje)
        
        # 2. Na Fila (Backlog) - Já é o filtro principal da rota (status='Agendando Visita')
        em_fila = len(chamados)
        
        # 3. Prioridade Alta
        prioridade_alta = sum(1 for c in chamados if c.prioridade == 'Alta')
        
        # 4. Técnicos Livres (Mock por enquanto ou lógica simples)
        # Poderíamos contar quantos usuários tecnicos NÃO tem agendamento hoje.
        tecnicos_livres = len(lista_tecnicos) # Simplificado por enquanto
        
        # Agrupar por Cidade (Oportunidades)
        oportunidades_dict = {}
        for c in chamados:
            city_name = c.usina.cidade or "Indefinida"
            if city_name not in oportunidades_dict:
                oportunidades_dict[city_name] = {"cidade": city_name, "total": 0, "urgentes": 0}
            
            oportunidades_dict[city_name]["total"] += 1
            if c.prioridade == 'Alta':
                oportunidades_dict[city_name]["urgentes"] += 1
        
        # Converter para lista ordenada por urgência/volume
        lista_oportunidades = sorted(
            oportunidades_dict.values(), 
            key=lambda x: (x["urgentes"], x["total"]), 
            reverse=True
        )

        # 5. Montar resposta final
        return jsonify({
            "lista": lista_chamados,
            "mapa": mapa_usinas,
            "agenda": agenda_eventos,
            "tecnicos": lista_tecnicos, # New field
            "kpis": {
                "visitas_hoje": visitas_hoje,
                "em_fila": em_fila,
                "prioridade_alta": prioridade_alta,
                "tecnicos_livres": tecnicos_livres
            },
            "oportunidades": lista_oportunidades,
            "filtros_aplicados": {
                "cidade": cidade,
                "prioridade": prioridade,
                "data": data_str
            }
        })

    except Exception as e:
        logging.error(f"ERRO CRÍTICO NO MENU DE PLANEJAMENTO:\n{traceback.format_exc()}")
        return jsonify({"erro": "Erro interno do servidor", "detalhes": str(e)}), 500


@planejamento_bp.route('/validar-viabilidade', methods=['POST'])
@jwt_required()
def validar_viabilidade():
    """
    Validate if a set of OS fits within technician's working hours.
    
    Request JSON:
        {
            "tecnico_id": int,
            "data": "YYYY-MM-DD",
            "os_ids": [int, ...]
        }
    """
    try:
        data = request.get_json()
        
        tecnico_id = data.get('tecnico_id')
        data_str = data.get('data')
        os_ids = data.get('os_ids', [])
        
        if not tecnico_id or not data_str:
            return jsonify({"erro": "tecnico_id e data são obrigatórios"}), 400
        
        capacity_service = CapacityCalculationService()
        resultado = capacity_service.validar_viabilidade(tecnico_id, data_str, os_ids)
        
        return jsonify(resultado)
        
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao validar viabilidade:\n{traceback.format_exc()}")
        return jsonify({"erro": "Erro interno do servidor", "detalhes": str(e)}), 500


@planejamento_bp.route('/sugerir-reagendamento', methods=['POST'])
@jwt_required()
def sugerir_reagendamento():
    """
    Suggest optimal rescheduling options for an OS.
    
    Request JSON:
        {
            "os_id": int,
            "dias_futuros": int (optional, default 7)
        }
    """
    try:
        data = request.get_json()
        
        os_id = data.get('os_id')
        dias_futuros = data.get('dias_futuros', 7)
        
        if not os_id:
            return jsonify({"erro": "os_id é obrigatório"}), 400
        
        rescheduling_service = ReschedulingService()
        resultado = rescheduling_service.sugerir_reagendamento(os_id, dias_futuros)
        
        return jsonify(resultado)
        
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao sugerir reagendamento:\n{traceback.format_exc()}")
        return jsonify({"erro": "Erro interno do servidor", "detalhes": str(e)}), 500


@planejamento_bp.route('/calcular-rota', methods=['POST'])
@jwt_required()
def calcular_rota():
    """
    Calculate complete route for a technician on a specific date.
    
    Request JSON:
        {
            "tecnico_id": int,
            "data": "YYYY-MM-DD"
        }
    """
    try:
        data = request.get_json()
        
        tecnico_id = data.get('tecnico_id')
        data_str = data.get('data')
        
        if not tecnico_id or not data_str:
            return jsonify({"erro": "tecnico_id e data são obrigatórios"}), 400
        
        # Get technician base coordinates
        tecnico = Usuario.query.get(tecnico_id)
        if not tecnico:
            return jsonify({"erro": "Técnico não encontrado"}), 404
        
        base_coords = {
            "latitude": float(tecnico.latitude_base) if tecnico.latitude_base else -24.465241,
            "longitude": float(tecnico.longitude_base) if tecnico.longitude_base else -53.952700
        }
        
        # Get OS for this technician on this date
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
        
        chamados = Chamado.query.join(Usina).filter(
            Chamado.id_usuario_responsavel == tecnico_id,
            Chamado.status == 'Agendando Visita',
            func.date(Chamado.data_agendamento) == data_obj
        ).all()
        
        if not chamados:
            return jsonify({
                "rota": {
                    "pontos": [{"tipo": "base", "nome": "Base", **base_coords}],
                    "geometria": None,
                    "distancia_total_km": 0.0,
                    "tempo_total_minutos": 0.0
                }
            })
        
        # Build OS list
        lista_os = []
        for chamado in chamados:
            if chamado.usina and chamado.usina.latitude and chamado.usina.longitude:
                lista_os.append({
                    "id": chamado.id_chamado,
                    "cliente": chamado.cliente.nome if chamado.cliente else "Cliente",
                    "latitude": float(chamado.usina.latitude),
                    "longitude": float(chamado.usina.longitude)
                })
        
        # Calculate route
        route_service = RouteOptimizationService()
        rota_completa = route_service.calcular_rota_completa(base_coords, lista_os)
        
        return jsonify({"rota": rota_completa})
        
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao calcular rota:\n{traceback.format_exc()}")
        return jsonify({"erro": "Erro interno do servidor", "detalhes": str(e)}), 500


@planejamento_bp.route('/configuracoes', methods=['GET', 'PUT'])
@jwt_required()
def configuracoes():
    """
    Get or update operational configuration.
    """
    try:
        if request.method == 'GET':
            config = ConfiguracaoOperacional.query.first()
            
            if not config:
                # Return defaults
                return jsonify({
                    "margem_seguranca_minutos": 30,
                    "velocidade_media_kmh": 50.0,
                    "tempo_medio_por_categoria": {
                        "Manutenção Preventiva": 90,
                        "Instalação": 180,
                        "Reparo": 120,
                        "Vistoria": 60
                    },
                    "feriados": []
                })
            
            return jsonify({
                "margem_seguranca_minutos": config.margem_seguranca_minutos,
                "velocidade_media_kmh": float(config.velocidade_media_kmh),
                "tempo_medio_por_categoria": config.tempo_medio_por_categoria or {},
                "feriados": config.feriados or []
            })
        
        elif request.method == 'PUT':
            data = request.get_json()
            
            config = ConfiguracaoOperacional.query.first()
            if not config:
                config = ConfiguracaoOperacional()
                db.session.add(config)
            
            if 'margem_seguranca_minutos' in data:
                config.margem_seguranca_minutos = data['margem_seguranca_minutos']
            
            if 'velocidade_media_kmh' in data:
                config.velocidade_media_kmh = data['velocidade_media_kmh']
            
            if 'tempo_medio_por_categoria' in data:
                config.tempo_medio_por_categoria = data['tempo_medio_por_categoria']
            
            if 'feriados' in data:
                config.feriados = data['feriados']
            
            db.session.commit()
            
            return jsonify({"mensagem": "Configuração atualizada com sucesso"})
    
    except Exception as e:
        logging.error(f"Erro ao gerenciar configurações:\n{traceback.format_exc()}")
        return jsonify({"erro": "Erro interno do servidor", "detalhes": str(e)}), 500


# ===========================================================================
# Novos endpoints — Planejador Inteligente
# ===========================================================================

@planejamento_bp.route('/os', methods=['GET'])
@jwt_required()
def listar_os_planejamento():
    """
    Lista backlog de OS para o Planejador Inteligente.
    Fonte oficial: tabela ordens_servico vinculada ao chamado.
    """
    try:
        os_rows = (
            OrdenServico.query
            .join(Chamado, OrdenServico.id_chamado == Chamado.id_chamado)
            .filter(
                OrdenServico.id_chamado.isnot(None),
                OrdenServico.status == 'Aberta',
                Chamado.is_active == True,
            )
            .order_by(
                db.case(
                    (Chamado.prioridade == 'URGENTE', 1),
                    (Chamado.prioridade == 'Alta', 2),
                    (Chamado.prioridade == 'M\u00e9dia', 3),
                    (Chamado.prioridade == 'Baixa', 4),
                    else_=5
                ),
                Chamado.data_criacao.asc(),
                OrdenServico.id_orden_servico.desc(),
            )
            .all()
        )

        result = []
        for os_row in os_rows:
            c = os_row.chamado
            if not c:
                continue

            flags = []
            has_geo = c.usina and c.usina.latitude and c.usina.longitude
            if not has_geo:
                flags.append('missing_geocode')
            if not c.tempo_estimado_minutos:
                flags.append('missing_time_estimate')

            result.append({
                # id mantido como id_chamado para compatibilidade do planejamento atual
                'id': c.id_chamado,
                'id_ordem_servico': os_row.id_orden_servico,
                'id_chamado': c.id_chamado,
                'titulo': c.titulo,
                'cliente': c.cliente.nome if c.cliente else None,
                'cidade': c.usina.cidade if c.usina else None,
                'lat': float(c.usina.latitude) if has_geo else None,
                'lng': float(c.usina.longitude) if has_geo else None,
                'prioridade': c.prioridade,
                'categoria': c.categoria,
                'status': os_row.status,
                'status_chamado': c.status,
                'commitment_level': c.commitment_level,
                'time_window_start': c.time_window_start.strftime('%H:%M') if c.time_window_start else None,
                'time_window_end': c.time_window_end.strftime('%H:%M') if c.time_window_end else None,
                'tempo_estimado_minutos': c.tempo_estimado_minutos,
                'status_execucao': c.status_execucao,
                'plannable': len(flags) == 0,
                'flags': flags,
            })

        return jsonify({'os': result, 'total': len(result)})

    except Exception:
        logging.error(f'Erro ao listar OS para planejamento:\n{traceback.format_exc()}')
        return jsonify({'erro': 'Erro interno do servidor'}), 500


@planejamento_bp.route('/semana/gerar', methods=['POST'])
@jwt_required()
def gerar_semana():
    """
    Generate (or regenerate) a full week plan.

    Body JSON:
        {
            "week_start_date": "YYYY-MM-DD",  # must be a Monday
            "technician_id": int,
            "force_regenerate": bool,           # optional, default false
            "constraints": {                     # optional overrides
                "work_start_h": 8,
                "soft_limit_h": 18.5,
                "lunch_min": 90
            }
        }
    """
    try:
        body = request.get_json()
        if not body:
            return jsonify({'erro': 'JSON inv\u00e1lido ou ausente'}), 400

        week_str = body.get('week_start_date')
        technician_id = body.get('technician_id')

        if not week_str or not technician_id:
            return jsonify({'erro': 'week_start_date e technician_id s\u00e3o obrigat\u00f3rios'}), 400

        try:
            week_start = date.fromisoformat(week_str)
        except ValueError:
            return jsonify({'erro': 'Formato de week_start_date inv\u00e1lido. Use YYYY-MM-DD'}), 400

        if week_start.weekday() != 0:
            return jsonify({'erro': 'week_start_date deve ser uma segunda-feira (weekday=0)'}), 400

        plan = SchedulingEngine.generate_week_plan(
            week_start_date=week_start,
            technician_id=int(technician_id),
            constraints=body.get('constraints'),
            force_regenerate=bool(body.get('force_regenerate', False)),
        )
        return jsonify(plan), 201

    except ValueError as e:
        return jsonify({'erro': str(e)}), 400
    except Exception:
        logging.error(f'Erro ao gerar semana:\n{traceback.format_exc()}')
        return jsonify({'erro': 'Erro interno do servidor'}), 500


@planejamento_bp.route('/semana', methods=['GET'])
@jwt_required()
def buscar_semana():
    """
    Retrieve an existing week plan.

    Query params:
        week_start_date=YYYY-MM-DD
        technician_id=int (opcional; ausente => visao agregada de todos os tecnicos)
    """
    try:
        week_str = request.args.get('week_start_date')
        technician_id = request.args.get('technician_id', type=int)

        if not week_str:
            return jsonify({'erro': 'week_start_date \u00e9 obrigat\u00f3rio'}), 400

        try:
            week_start = date.fromisoformat(week_str)
        except ValueError:
            return jsonify({'erro': 'Formato de week_start_date inv\u00e1lido'}), 400

        view = SchedulingEngine.serialize_week_view(
            week_start_date=week_start,
            technician_id=technician_id,
        )
        return jsonify(view)

    except ValueError as e:
        return jsonify({'erro': str(e)}), 404
    except Exception:
        logging.error(f'Erro ao buscar semana:\n{traceback.format_exc()}')
        return jsonify({'erro': 'Erro interno do servidor'}), 500


@planejamento_bp.route('/semana/mover', methods=['POST'])
@jwt_required()
def mover_os():
    """
    Move an OS from one day to another within a week plan and recalculate.

    Body JSON:
        {
            "plan_id": int,
            "os_id": int,
            "from_date": "YYYY-MM-DD" | null,
            "to_date": "YYYY-MM-DD" | null,  # null => desagendar para backlog
            "target_index": int   # optional, 0-based
        }
    """
    try:
        body = request.get_json()
        if not body:
            return jsonify({'erro': 'JSON inv\u00e1lido ou ausente'}), 400

        required = ['plan_id', 'os_id', 'from_date', 'to_date']
        missing = [f for f in required if f not in body]
        if missing:
            return jsonify({'erro': f'Campos obrigat\u00f3rios ausentes: {missing}'}), 400

        plan = SchedulingEngine.move_os(
            plan_id=int(body['plan_id']),
            os_id=int(body['os_id']),
            from_date_str=body['from_date'],
            to_date_str=body['to_date'],
            target_index=body.get('target_index'),
        )
        return jsonify(plan), 200

    except ValueError as e:
        return jsonify({'erro': str(e)}), 400
    except Exception:
        logging.error(f'Erro ao mover OS:\n{traceback.format_exc()}')
        return jsonify({'erro': 'Erro interno do servidor'}), 500
