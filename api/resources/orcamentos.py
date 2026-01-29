# /api/resources/orcamentos.py (VERSÃO FINAL E CORRIGIDA)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from decimal import Decimal
import logging
import traceback

from .. import db
from ..models import (
    Orcamento, OrcamentoMaterial, OrcamentoServico, 
    Cliente, Usina, Material, Servico, Chamado,
    OrdenServico, OrdemServicoItem # <-- Importa modelos de OS
)
from ..schemas.orcamento_schema import OrcamentoInputSchema, OrcamentoOutputSchema, OrcamentoUpdateSchema
from ..schemas.ordem_servico_schema import OrdemServicoSchema # <-- Importa schema de OS
from ..services.geolocation_service import calcular_distancia_e_custo
from ..services.deslocamento_service import calcular_atendimento, calcular_rota_osrm
from sqlalchemy.orm import joinedload

# --- Importações de decorador corrigidas ---
from ..decorators import admin_required, tecnico_required, supervisor_or_admin_required

orcamentos_bp = Blueprint('orcamentos', __name__)

# ---
# FUNÇÃO DE CALCULO DE DESLOCAMENTO PARA ORÇAMENTO
# ---
@orcamentos_bp.route("/calcular-deslocamento", methods=["POST", "OPTIONS"])
def calcular_deslocamento_orcamento():
    """
    Calcula deslocamento + hora técnica para um orçamento.
    Suporta o novo sistema de modalidades se 'modalidade' for informado.
    """
    from ..utils.calculadora_orcamento import calcular_modalidade

    if request.method == "OPTIONS":
        return ("", 200)

    data = request.get_json(silent=True) or {}

    # Parâmetros comuns
    modalidade = data.get("modalidade") or data.get("tipo_atendimento") # Compatibilidade
    perfil_cobranca = data.get("perfil_cobranca") or "tabela1"
    horas_previstas = float(data.get("horas_previstas") or 1)
    qtd_tecnicos = int(data.get("qtd_tecnicos") or 1)
    potencia_kwp = float(data.get("potencia_kwp") or 0)

    usina_id = data.get("usina_id")
    distancia_manual = data.get("distancia_km")

    # 1) Se tem usina -> busca coordenadas e usa OSRM
    geometry = None
    duracao_min = None
    distancia_km_ida = 0.0

    if usina_id:
        usina = Usina.query.get(usina_id)
        if not usina or usina.latitude is None or usina.longitude is None:
            return jsonify({"message": "Usina sem coordenadas."}), 400

        distancia_km_ida, duracao_min, geometry = calcular_rota_osrm(
            dest_lat=usina.latitude,
            dest_lon=usina.longitude,
        )
    else:
        # 2) Sem usina: usa distância manual
        if distancia_manual is None:
            return jsonify({"message": "Informe 'usina_id' ou 'distancia_km'."}), 400
        distancia_km_ida = float(distancia_manual)

    # 3) CÁLCULO UNIFICADO
    # Se tiver modalidade (novo sistema), usa a calculadora nova
    if modalidade and modalidade in ['assistencia_paga', 'garantia_instalacao', 'ajuste_monitoramento', 'troca_dps', 'garantia_inversor_outros', 'garantia_inversor_bedin', 'garantia_painel_bedin', 'levantamento_sinistro']:
        try:
            resultado = calcular_modalidade(
                modalidade=modalidade,
                distancia_km=distancia_km_ida,
                num_tecnicos=qtd_tecnicos,
                horas=horas_previstas,
                potencia_kwp=potencia_kwp
            )
            
            # Mapeia o resultado para o formato esperado pelo frontend (mapa)
            response = {
                "tipo_atendimento": modalidade,
                "perfil_cobranca": perfil_cobranca,
                "horas_previstas": resultado.get("horas_cobradas", horas_previstas),
                "qtd_tecnicos": resultado.get("num_tecnicos", qtd_tecnicos),
                "distancia_km_ida": distancia_km_ida,
                "distancia_km_total": distancia_km_ida * 2,
                "valor_deslocamento": resultado.get("valor_deslocamento", 0),
                "valor_hora_unitaria": resultado.get("valor_hora_tecnica", 0),
                "valor_horas_total": resultado.get("total_horas_tecnicas", 0),
                "valor_total_atendimento": resultado.get("total", 0),
                "duracao_min": duracao_min,
                "geometry": geometry,
                "detalhamento": resultado.get("detalhamento")
            }
            return jsonify(response), 200
            
        except Exception as e:
            logging.error(f"Erro ao calcular modalidade em calcular-deslocamento: {e}")
            # Fallback para o sistema antigo se der erro
            pass

    # Fallback: Sistema antigo (calcular_atendimento)
    atendimento = calcular_atendimento(
        distancia_km_ida=distancia_km_ida,
        horas_previstas=horas_previstas,
        perfil_cobranca=perfil_cobranca,
        qtd_tecnicos=qtd_tecnicos,
    )

    response = {
        "tipo_atendimento": atendimento.get("tipo_atendimento", "assistencia_paga"),
        "perfil_cobranca": perfil_cobranca,
        "horas_previstas": atendimento["horas_cobradas"],
        "qtd_tecnicos": atendimento["qtd_tecnicos"],
        "distancia_km_ida": atendimento["distancia_km_ida"],
        "distancia_km_total": atendimento["distancia_km_total"],
        "valor_deslocamento": atendimento["valor_deslocamento"],
        "valor_hora_unitaria": atendimento["valor_hora_unitaria"],
        "valor_horas_total": atendimento["valor_horas_total"],
        "valor_total_atendimento": atendimento["valor_total_atendimento"],
        "duracao_min": duracao_min,
        "geometry": geometry,
    }

    return jsonify(response), 200

# ---
# ENDPOINT DE CÁLCULO DE MODALIDADE (NOVO)
# ---
@orcamentos_bp.route('/calcular-modalidade', methods=['POST', 'OPTIONS'])
def calcular_modalidade_endpoint():
    """
    Calcula os valores com base na modalidade, distância e horas.
    Retorna o cálculo detalhado para o frontend.
    """
    from ..utils.calculadora_orcamento import calcular_modalidade
    import traceback
    
    if request.method == "OPTIONS":
        return ("", 200)
    
    data = request.get_json(silent=True) or {}
    
    modalidade = data.get('modalidade')
    if not modalidade:
        return jsonify({"error": "Campo 'modalidade' é obrigatório"}), 400
    
    try:
        distancia_km = float(data.get('distancia_km', 0))
        num_tecnicos = int(data.get('num_tecnicos', 1))
        horas = float(data.get('horas', 1.0))
        potencia_kwp = float(data.get('potencia_kwp', 0))
        valor_hora_override = data.get('valor_hora_override')
        if valor_hora_override is not None:
            valor_hora_override = float(valor_hora_override)
            
        valor_deslocamento_override = data.get('valor_deslocamento_override')
        if valor_deslocamento_override is not None:
             valor_deslocamento_override = float(valor_deslocamento_override)
        
        resultado = calcular_modalidade(
            modalidade=modalidade,
            distancia_km=distancia_km,
            num_tecnicos=num_tecnicos,
            horas=horas,
            potencia_kwp=potencia_kwp,
            valor_hora_override=valor_hora_override,
            valor_deslocamento_override=valor_deslocamento_override
        )
        
        return jsonify(resultado), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao calcular modalidade: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Erro interno ao calcular valores"}), 500

# ---
# FUNÇÃO DE CRIAÇÃO DE ORÇAMENTO
# ---
@orcamentos_bp.route('', methods=['POST'])
@jwt_required()
@tecnico_required()
def criar_orcamento():
    """Cria um novo orçamento usando a nova calculadora unificada."""
    from ..utils.calculadora_orcamento import calcular_modalidade
    
    id_usuario_criador = get_jwt_identity()
    json_data = request.get_json()

    schema = OrcamentoInputSchema()
    try:
        data = schema.load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400

    # Validações de FK
    cliente = Cliente.query.get_or_404(data['id_cliente'])
    usina = Usina.query.get_or_404(data['id_usina'])
    if usina.id_cliente != cliente.id_cliente:
        return jsonify({"message": "Usina não pertence ao cliente selecionado."}), 400
    
    if data.get('id_chamado'):
        Chamado.query.get_or_404(data['id_chamado'])

    try:
        valor_total_itens = Decimal('0.0')
        materiais_db = []
        servicos_db = []

        # Calcula o valor dos materiais
        for item_data in data.get('materiais', []):
            material = Material.query.get_or_404(item_data['id'])
            valor_total_itens += Decimal(item_data['quantidade']) * material.valor_venda
            materiais_db.append((material, item_data['quantidade']))

        # Calcula o valor dos serviços
        for item_data in data.get('servicos', []):
            servico = Servico.query.get_or_404(item_data['id'])
            valor_total_itens += Decimal(item_data['quantidade']) * servico.valor_servico
            servicos_db.append((servico, item_data['quantidade']))
            
        # --- CÁLCULO DO DESLOCAMENTO/MODALIDADE (NOVO) ---
        modalidade = data.get('modalidade') or data.get('tipo_atendimento') or 'assistencia_paga'
        
        # Obter distância (OSRM)
        distancia_km = 0.0
        if usina.latitude and usina.longitude:
            distancia_km, _, _ = calcular_rota_osrm(usina.latitude, usina.longitude)
        else:
            distancia_km = float(data.get('distancia_km', 0))

        # Calcular usando a nova calculadora unificada
        resultado_calculo = calcular_modalidade(
            modalidade=modalidade,
            distancia_km=distancia_km,
            num_tecnicos=int(data.get('qtd_tecnicos', 1)),
            horas=float(data.get('horas_previstas', 1.0)),
            potencia_kwp=float(data.get('potencia_kwp', 0))
        )
        
        valor_deslocamento_decimal = Decimal(str(resultado_calculo.get('valor_deslocamento', 0)))
        # Nota: O 'total' do resultado inclui horas técnicas + deslocamento.
        # Mas aqui salvamos 'valor_deslocamento' separado.
        # O valor das horas técnicas (se houver serviço de hora técnica) deve ser adicionado como item?
        # No sistema atual, hora técnica parece ser cobrada à parte ou incluída no total final?
        # O modelo tem 'valor_total_itens' e 'valor_deslocamento'.
        # Se a modalidade cobra hora técnica (Assistência Paga), onde isso entra?
        # No frontend, hora técnica NÃO é um item de serviço/material, é parte do cálculo da modalidade.
        # Então precisamos somar o valor das horas técnicas ao total final, ou salvar em algum lugar.
        # O modelo atual NÃO tem campo separado para 'valor_servicos_modalidade'.
        # Vamos somar ao 'valor_deslocamento' ou criar um item de serviço fictício?
        # Melhor: Somar ao valor_deslocamento para fins de total, ou assumir que o frontend manda a hora técnica como item?
        # O frontend NÃO manda hora técnica como item.
        # Então o valor da modalidade (horas + deslocamento) deve compor o total.
        # Vamos usar o 'total' retornado pela calculadora como base para o custo de atendimento.
        
        custo_atendimento = Decimal(str(resultado_calculo.get('total', 0)))
        
        # Se o custo_atendimento inclui deslocamento + horas, e temos valor_deslocamento separado...
        # valor_total_final = valor_total_itens + custo_atendimento - desconto
        
        # Mas precisamos preencher o campo 'valor_deslocamento' do banco.
        # Vamos usar o valor de deslocamento real.
        
        # Calcula o total final
        desconto_decimal = Decimal(data.get('desconto', '0.0'))
        
        # Total Final = Itens + Custo da Modalidade (Deslocamento + Horas) - Desconto
        valor_total_final = valor_total_itens + custo_atendimento - desconto_decimal

        # Cria o objeto Orçamento
        novo_orcamento = Orcamento(
            id_cliente=cliente.id_cliente,
            id_usina=usina.id_usina,
            id_usuario_responsavel=id_usuario_criador,
            id_chamado=data.get('id_chamado'),
            descricao_servico=data['descricao_servico'],
            valor_total_itens=valor_total_itens,
            desconto=desconto_decimal,
            valor_deslocamento=valor_deslocamento_decimal, 
            valor_total_final=valor_total_final, 
            status='pendente',
            modalidade=modalidade,
            qtd_tecnicos=int(data.get('qtd_tecnicos', 1)),
            horas_previstas=Decimal(str(data.get('horas_previstas', 1.0))),
            parametros={
                "potencia_kwp": float(data.get('potencia_kwp', 0)),
                "valor_hora_override": float(data.get('valor_hora_override')) if data.get('valor_hora_override') else None
            }
        )
            
        db.session.add(novo_orcamento)
        db.session.flush()

        # Adiciona os itens ao orçamento
        for material, quantidade in materiais_db:
            db.session.add(OrcamentoMaterial(
                id_orcamento=novo_orcamento.id_orcamento,
                id_material=material.id_material,
                quantidade=quantidade,
                valor_unitario_cobrado=material.valor_venda
            ))
            
        for servico, quantidade in servicos_db:
             db.session.add(OrcamentoServico(
                id_orcamento=novo_orcamento.id_orcamento,
                id_servico=servico.id_servico,
                quantidade=quantidade,
                valor_cobrado=servico.valor_servico
            ))

        db.session.commit()
        
        result = OrcamentoOutputSchema().dump(novo_orcamento)
        # Adiciona dados extras
        result['mapa_localizacao'] = {
            'distancia_km_ida': distancia_km,
            'valor_deslocamento': float(valor_deslocamento_decimal),
            'custo_atendimento': float(custo_atendimento)
        }
        
        return jsonify(result), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"ERRO AO CRIAR ORÇAMENTO: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro interno ao salvar o orçamento", "error": str(e)}), 500

# ---
# FUNÇÃO DE LISTAGEM DE ORÇAMENTOS
# ---
@orcamentos_bp.route('', methods=['GET'])
@jwt_required()
@tecnico_required() # <-- Decorador com ()
def listar_orcamentos(): # <-- Assinatura da função CORRIGIDA (sem 'f')
    """Lista todos os orçamentos."""
    try:
        query = Orcamento.query.options(
            joinedload(Orcamento.cliente),
            joinedload(Orcamento.usina)
        ).order_by(Orcamento.data_criacao.desc())
        
        orcamentos = query.all()
        return jsonify(OrcamentoOutputSchema(many=True).dump(orcamentos)), 200
    except Exception as e:
        return jsonify({"message": "Erro ao listar orçamentos", "error": str(e)}), 500

# ---
# FUNÇÃO DE DETALHE DO ORÇAMENTO
# ---
@orcamentos_bp.route('/<int:id_orcamento>', methods=['GET'])
@jwt_required()
@tecnico_required() # <-- Decorador com ()
def detalhar_orcamento(id_orcamento): # <-- Assinatura da função CORRIGIDA (sem 'f')
    """Retorna os detalhes de um orçamento específico."""
    orcamento = Orcamento.query.options(
        joinedload(Orcamento.materiais).joinedload(OrcamentoMaterial.material),
        joinedload(Orcamento.servicos).joinedload(OrcamentoServico.servico),
        joinedload(Orcamento.usina),
        joinedload(Orcamento.cliente),
        joinedload(Orcamento.usuario)
    ).get_or_404(id_orcamento)
    
    result = OrcamentoOutputSchema().dump(orcamento)
    deslocamento_info = calcular_distancia_e_custo(orcamento.usina.latitude, orcamento.usina.longitude)
    
    result['mapa_localizacao'] = {
        "latitude": orcamento.usina.latitude, "longitude": orcamento.usina.longitude,
        "url": f"https://openstreetmap.org/?mlat={orcamento.usina.latitude}&mlon={orcamento.usina.longitude}",
        "distancia_km": deslocamento_info['distancia_km'],
        "tempo_estimado": deslocamento_info['tempo_estimado'],
        "valor_deslocamento": deslocamento_info['valor_deslocamento'],
        "geometry": deslocamento_info.get('geometry')
    }
    return jsonify(result)

# ---
# FUNÇÃO DE ATUALIZAÇÃO DO ORÇAMENTO
# ---
@orcamentos_bp.route('/<int:id_orcamento>', methods=['PUT'])
@jwt_required()
@supervisor_or_admin_required() # <-- Decorador com ()
def atualizar_orcamento(id_orcamento): # <-- Assinatura da função CORRIGIDA (sem 'f')
    """Atualiza um orçamento existente."""
    # (Toda a lógica de atualização que já tínhamos)
    orcamento = Orcamento.query.get_or_404(id_orcamento)
    json_data = request.get_json()
    
    try:
        data = OrcamentoUpdateSchema(partial=True).load(json_data)
    except ValidationError as err:
        return jsonify({"message": "Erro de validação", "errors": err.messages}), 400
    
    try:
        # 1. Atualiza campos simples
        orcamento.descricao_servico = data.get('descricao_servico', orcamento.descricao_servico)
        orcamento.id_chamado = data.get('id_chamado', orcamento.id_chamado)
        if 'status' in data:
            orcamento.status = data['status']
        if 'id_cliente' in data:
            orcamento.id_cliente = data['id_cliente']
        if 'id_usina' in data:
             orcamento.id_usina = data['id_usina']

        # 2. Se itens foram enviados, recalcula
        if 'materiais' in data or 'servicos' in data:
            OrcamentoMaterial.query.filter_by(id_orcamento=id_orcamento).delete()
            OrcamentoServico.query.filter_by(id_orcamento=id_orcamento).delete()
            
            valor_total_itens = Decimal('0.0')
            
            for item_data in data.get('materiais', []):
                material = Material.query.get_or_404(item_data['id'])
                valor_total_itens += Decimal(item_data['quantidade']) * material.valor_venda
                db.session.add(OrcamentoMaterial(id_orcamento=id_orcamento, id_material=item_data['id'], quantidade=item_data['quantidade'], valor_unitario_cobrado=material.valor_venda))
            
            for item_data in data.get('servicos', []):
                servico = Servico.query.get_or_404(item_data['id'])
                valor_total_itens += Decimal(item_data['quantidade']) * servico.valor_servico
                db.session.add(OrcamentoServico(id_orcamento=id_orcamento, id_servico=item_data['id'], quantidade=item_data['quantidade'], valor_cobrado=servico.valor_servico))
            
            orcamento.valor_total_itens = valor_total_itens
        
        # 3. Recalcula o deslocamento e o total final
        # 3. Recalcula o deslocamento e o total final usando a CALCULADORA UNIFICADA
        from ..utils.calculadora_orcamento import calcular_modalidade

        usina_atualizada = Usina.query.get(orcamento.id_usina)
        
        # Parâmetros para recálculo
        nova_modalidade = data.get('modalidade') or getattr(orcamento, 'modalidade', None) or 'assistencia_paga'
        
        # Tenta atualizar a modalidade no objeto se o campo existir
        # Tenta atualizar a modalidade no objeto se o campo existir
        if hasattr(orcamento, 'modalidade') and 'modalidade' in data:
            orcamento.modalidade = nova_modalidade

        horas_previstas = float(data.get('horas_previstas') or getattr(orcamento, 'horas_previstas', 1.0)) # Fallback seguro
        qtd_tecnicos = int(data.get('qtd_tecnicos') or getattr(orcamento, 'qtd_tecnicos', 1))

        # Atualiza campos de cálculo no modelo
        orcamento.qtd_tecnicos = qtd_tecnicos
        orcamento.horas_previstas = Decimal(str(horas_previstas))
        
        # Atualiza parâmetros JSON (mantendo existentes se não enviados)
        params_atuais = dict(orcamento.parametros) if orcamento.parametros else {}
        if 'potencia_kwp' in data:
            params_atuais['potencia_kwp'] = float(data['potencia_kwp'])
        if 'valor_hora_override' in data:
            val = data['valor_hora_override']
            params_atuais['valor_hora_override'] = float(val) if val else None
        
        orcamento.parametros = params_atuais
        
        # Recupera valores para cálculo
        potencia_cal = params_atuais.get('potencia_kwp', 0)
        override_cal = params_atuais.get('valor_hora_override')
        
        # Calcula distância
        distancia_km = 0.0
        if usina_atualizada.latitude and usina_atualizada.longitude:
            distancia_km, _, _ = calcular_rota_osrm(usina_atualizada.latitude, usina_atualizada.longitude)
        else:
            distancia_km = float(data.get('distancia_km', 0))

        # Executa o cálculo unificado
        resultado_calculo = calcular_modalidade(
            modalidade=nova_modalidade,
            distancia_km=distancia_km,
            num_tecnicos=qtd_tecnicos,
            horas=horas_previstas,
            potencia_kwp=potencia_cal,
            valor_hora_override=override_cal
        )

        custo_atendimento = Decimal(str(resultado_calculo.get('total', 0)))
        valor_deslocamento_decimal = Decimal(str(resultado_calculo.get('valor_deslocamento', 0)))
        
        total_itens_decimal = orcamento.valor_total_itens or Decimal('0.0')
        desconto_decimal = Decimal(data.get('desconto', str(orcamento.desconto or '0.0')))
        
        orcamento.valor_deslocamento = valor_deslocamento_decimal
        orcamento.desconto = desconto_decimal
        # Total Final = Itens + Custo Modalidade (Horas + Deslocamento) - Desconto
        orcamento.valor_total_final = total_itens_decimal + custo_atendimento - desconto_decimal

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        tb_str = traceback.format_exc()
        logging.error(f"ERRO AO ATUALIZAR ORÇAMENTO ID {id_orcamento}:\n{tb_str}")
        return jsonify({ "message": "Erro interno ao atualizar o orçamento", "error": str(e) }), 500

    return jsonify(OrcamentoOutputSchema().dump(orcamento))

# ---
# FUNÇÃO DE DELEÇÃO DO ORÇAMENTO
# ---
@orcamentos_bp.route('/<int:id_orcamento>', methods=['DELETE'])
@jwt_required()
@admin_required() # <-- Decorador com ()
def deletar_orcamento(id_orcamento): # <-- Assinatura da função CORRIGIDA (sem 'f')
    """Deleta um orçamento."""
    orcamento = Orcamento.query.get_or_404(id_orcamento)
    
    # Verifica se existe OS vinculada
    if OrdenServico.query.filter_by(id_orcamento=id_orcamento).first():
        return jsonify({"message": "Não é possível deletar. Este orçamento já possui uma Ordem de Serviço vinculada."}), 400
        
    try:
        db.session.delete(orcamento)
        db.session.commit()
        return jsonify({"message": f"Orçamento ID {id_orcamento} deletado."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erro ao deletar orçamento", "error": str(e)}), 500

# ---
# FUNÇÃO DE GERAÇÃO DE OS (A PARTIR DO ORÇAMENTO)
# ---
@orcamentos_bp.route('/<int:id_orcamento>/gerar-os', methods=['POST'])
@jwt_required()
@supervisor_or_admin_required() # <-- Decorador com ()
def gerar_os_de_orcamento(id_orcamento): # <-- Assinatura da função CORRIGIDA (sem 'f')
    """
    Cria uma nova Ordem de Serviço a partir de um orçamento APROVADO.
    """
    orcamento = Orcamento.query.options(
        joinedload(Orcamento.materiais).joinedload(OrcamentoMaterial.material),
        joinedload(Orcamento.servicos).joinedload(OrcamentoServico.servico)
    ).get_or_404(id_orcamento)

    if orcamento.status != 'aprovado':
        return jsonify({"message": "Orçamento precisa estar 'aprovado' para gerar uma OS."}), 400
    
    if orcamento.ordem_servico:
        return jsonify({"message": "Uma Ordem de Serviço já existe para este orçamento."}), 409

    try:
        nova_os = OrdenServico(
            id_orcamento=orcamento.id_orcamento,
            id_chamado=orcamento.id_chamado,
            id_cliente=orcamento.id_cliente,
            id_usina=orcamento.id_usina,
            id_usuario_responsavel=orcamento.id_usuario_responsavel,
            status='Aberta'
        )
        db.session.add(nova_os)
        db.session.flush()

        itens_para_os = []
        for item in orcamento.materiais:
            itens_para_os.append(OrdemServicoItem(
                id_ordem_servico=nova_os.id_orden_servico,
                descricao=item.material.nome_material,
                tipo='material',
                quantidade=item.quantidade
            ))
        for item in orcamento.servicos:
            itens_para_os.append(OrdemServicoItem(
                id_ordem_servico=nova_os.id_orden_servico,
                descricao=item.servico.nome_servico,
                tipo='servico',
                quantidade=item.quantidade
            ))
            
        db.session.add_all(itens_para_os)
        db.session.commit()
        
        return jsonify(OrdemServicoSchema().dump(nova_os)), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"ERRO AO GERAR OS: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Erro interno ao gerar a OS", "error": str(e)}), 500
