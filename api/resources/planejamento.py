from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import case, func, or_
import logging
import traceback
from datetime import datetime

from .. import db
from ..models import Chamado, Usina, Cliente, Usuario, OrdenServico

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
