# /api/utils/calculadora_orcamento.py
"""
Módulo centralizado para cálculos de orçamentos
Implementa as modalidades de atendimento com regras específicas,
obtendo parâmetros dinamicamente do banco de dados quando possível.
"""

import json
import math

# ============================================================================
# DEFAULTS (Valores padrão caso o banco não tenha config)
# ============================================================================

DEFAULT_TABELA_HORA_TECNICA = {
    "1_tecnico": {
        "ate_30km": 60.00,
        "30_a_100km": 80.00,
        "acima_100km": 100.00
    },
    "2_tecnicos": {
        "ate_30km": 90.00,
        "30_a_100km": 120.00,
        "acima_100km": 150.00
    }
}

DEFAULT_TABELA_SERVICO_FIXO = {
    "ate_30km": 60.00,
    "ate_100km": 90.00,
    "acima_100km": None
}

# ============================================================================
# HELPER DE CONFIGURAÇÃO DINÂMICA
# ============================================================================

def get_param(chave, default):
    try:
        from ..models import Parametro
        # Tenta buscar no banco
        p = Parametro.query.filter_by(chave=chave).first()
        if p and p.valor:
            val = p.valor
            # Conversão inteligente de tipos
            try:
                # Se default for dict/list, esperamos JSON
                if isinstance(default, (dict, list)):
                    if isinstance(val, (dict, list)): return val
                    return json.loads(val)
                # Se default for número
                if isinstance(default, (int, float)):
                    return float(val)
                # Boolean
                if isinstance(default, bool):
                     return str(val).lower() == 'true'
            except:
                pass 
            return val
    except Exception as e:
        # Fallback silencioso (pode ocorrer se fora de app context ou erro DB)
        pass
    return default

# Getters
def get_tabela_hora_tecnica():
    return get_param('orcamento.tabela_hora_tecnica', DEFAULT_TABELA_HORA_TECNICA)

def get_tabela_servico_fixo():
    return get_param('orcamento.tabela_servico_fixo', DEFAULT_TABELA_SERVICO_FIXO)

def get_valor_deslocamento_km():
    return get_param('orcamento.valor_km', 2.00)

def get_deslocamento_bedin_fixo():
    return get_param('orcamento.deslocamento_bedin', 152.00)

def get_limite_potencia_1_tecnico():
    return get_param('orcamento.limite_potencia_1_tecnico', 12.0)


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def detectar_num_tecnicos(potencia_kwp):
    """Detecta número de técnicos necessários baseado na potência da instalação."""
    if potencia_kwp <= get_limite_potencia_1_tecnico():
        return 1
    else:
        return 2


def calcular_faixa_distancia(distancia_km):
    """Determina a faixa de distância para aplicação de tabela de preços."""
    if distancia_km <= 30:
        return "ate_30km"
    elif distancia_km <= 100:
        return "30_a_100km"
    else:
        return "acima_100km"


# ============================================================================
# FUNÇÕES DE CÁLCULO POR MODALIDADE
# ============================================================================

def calcular_assistencia_paga(distancia_km, num_tecnicos, horas, valor_hora_override=None, valor_deslocamento_override=None):
    """Calcula valores para Assistência Paga."""
    faixa = calcular_faixa_distancia(distancia_km)
    chave_tecnico = f"{num_tecnicos}_tecnico{'s' if num_tecnicos > 1 else ''}"
    
    tabela = get_tabela_hora_tecnica()
    
    # Valor da hora técnica (override ou tabela)
    if valor_hora_override is not None:
        valor_hora = float(valor_hora_override)
    else:
        # Tenta buscar configuração específica da Modalidade no banco
        try:
            from ..models import Modalidade
            mod_db = Modalidade.query.filter_by(chave='assistencia_paga').first()
            if mod_db and mod_db.configuracao:
                config_mod = mod_db.configuracao
                # Se for string, converte para dict
                if isinstance(config_mod, str):
                    try:
                        config_mod = json.loads(config_mod)
                    except:
                        config_mod = {}

                if isinstance(config_mod, dict) and 'tabela_hora_tecnica' in config_mod:
                    tabela = config_mod['tabela_hora_tecnica']
        except Exception as e:
            # logging.warning(f"Erro ao buscar config modalidade: {e}")
            pass

        # Pega da tabela dinâmica. Se chave não existir, fallback seguro
        try:
            valor_hora = float(tabela.get(chave_tecnico, {}).get(faixa, 0))
        except:
            valor_hora = 0.0

    # Mínimo de 1 hora
    horas_cobradas = max(horas, 1.0)
    valor_horas = valor_hora * horas_cobradas
    
    # Deslocamento
    distancia_total_km = distancia_km * 2
    
    if valor_deslocamento_override is not None:
        valor_deslocamento = float(valor_deslocamento_override)
        # Tenta inferir valor_km reverso para info, ou mantem genérico
        valor_km = valor_deslocamento / distancia_total_km if distancia_total_km > 0 else 0
    else:
        # Verifica preço por km na configuração da modalidade
        valor_km = get_valor_deslocamento_km() # Default
        try:
            if 'config_mod' in locals() and isinstance(config_mod, dict) and 'preco_km' in config_mod:
                 valor_km = float(config_mod['preco_km'])
        except:
            pass

        valor_deslocamento = distancia_total_km * valor_km
        # Rounding logic requested by User: 38.4km (153.60) -> 154.00 (Ceiling)
        # Strategy: Round UP to nearest integer.
        valor_deslocamento = math.ceil(valor_deslocamento)
    
    total = valor_horas + valor_deslocamento
    
    return {
        "modalidade": "assistencia_paga",
        "faixa_distancia": faixa,
        "num_tecnicos": num_tecnicos,
        "valor_hora_tecnica": valor_hora,
        "horas_previstas": horas,
        "horas_cobradas": horas_cobradas,
        "total_horas_tecnicas": valor_horas,
        "distancia_ida_km": distancia_km,
        "distancia_total_km": distancia_total_km,
        "valor_deslocamento": valor_deslocamento,
        "total": total,
        "detalhamento": [
            f"Hora técnica ({num_tecnicos} téc, {faixa.replace('_', ' ')}): R$ {valor_hora:.2f}/h × {horas_cobradas}h = R$ {valor_horas:.2f}",
            f"Deslocamento: {distancia_km}km × 2 (ida/volta) × R$ {valor_km:.2f}/km = R$ {valor_deslocamento:.2f}",
            f"Total: R$ {total:.2f}"
        ]
    }


def calcular_garantia_instalacao(distancia_km, num_tecnicos, horas):
    """Calcula valores para Garantia da Instalação (Isento)."""
    # Usa a base da assistência paga para estrutura, depois zero
    resultado = calcular_assistencia_paga(distancia_km, num_tecnicos, horas)
    
    # Zerar todos os valores monetários
    resultado["modalidade"] = "garantia_instalacao"
    resultado["valor_hora_tecnica"] = 0.00
    resultado["total_horas_tecnicas"] = 0.00
    resultado["valor_deslocamento"] = 0.00
    resultado["total"] = 0.00
    resultado["detalhamento"] = [
        "Garantia da instalação: Sem custo (até 1 ano)",
        "Exceção: Ajuste de monitoramento é cobrado separadamente"
    ]
    resultado["observacao"] = "Serviço coberto pela garantia da instalação"
    
    return resultado


def calcular_servico_fixo(distancia_km, tipo_servico="ajuste_monitoramento"):
    """Calcula valores para serviços com valor fixo por distância."""
    faixa = calcular_faixa_distancia(distancia_km)
    
    if faixa == "acima_100km":
        return {
            "modalidade": tipo_servico,
            "faixa_distancia": faixa,
            "valor_servico": 0.00,
            "valor_deslocamento": 0.00,
            "total": 0.00,
            "detalhamento": [
                "Distância acima de 100km: Valor A DEFINIR manualmente.",
            ],
            "observacao": "ATENÇÃO: Distância > 100km. Valor deve ser definido manualmente.",
            "requer_atencao": True
        }
    
    tabela = get_tabela_servico_fixo()
    # Pega valor da tabela
    try:
        # Mapeia chaves se necessário, mas defaults usam "ate_30km" etc.
        valor_servico = float(tabela.get(faixa, tabela.get("ate_100km", 90.00))) 
        # Lógica original: ate_30km -> x, senao (30_a_100) -> y.
        # Ajuste para usar dict exato se possível
    except:
        valor_servico = 0.0
    
    return {
        "modalidade": tipo_servico,
        "faixa_distancia": faixa,
        "valor_servico": valor_servico,
        "valor_deslocamento": 0.00,
        "total": valor_servico,
        "detalhamento": [
            f"Serviço fixo ({faixa.replace('_', ' ')}): R$ {valor_servico:.2f}",
            "Deslocamento: R$ 0,00 (não cobrado nesta faixa)"
        ]
    }


def calcular_garantia_inversor(distancia_km, num_tecnicos, horas_por_visita, com_bedin=False, tipo_equipamento="inversor", valor_hora_override=None):
    """Calcula valores para garantia de equipamento (2 visitas)."""
    # Calcular uma visita
    visita = calcular_assistencia_paga(distancia_km, num_tecnicos, horas_por_visita, valor_hora_override)
    
    # 2 visitas (inspeção + reinstalação)
    num_visitas = 2
    total_visitas = visita["total"] * num_visitas
    
    # Deslocamento Bedin
    valor_bedin = get_deslocamento_bedin_fixo()
    total_bedin = valor_bedin if com_bedin else 0.00
    
    # Total geral
    total = total_visitas + total_bedin
    
    detalhamento = [
        f"Visita 1 (inspeção): R$ {visita['total']:.2f} ({visita['num_tecnicos']} téc, {visita['horas_cobradas']}h)",
        f"Visita 2 (reinstalação): R$ {visita['total']:.2f} ({visita['num_tecnicos']} téc, {visita['horas_cobradas']}h)",
        f"Subtotal visitas: R$ {total_visitas:.2f}"
    ]
    
    if com_bedin:
        detalhamento.append(f"Deslocamento Bedin Solar: R$ {valor_bedin:.2f}")
    
    detalhamento.append(f"Total: R$ {total:.2f}")
    
    modalidade = "garantia_"
    if tipo_equipamento == "painel":
        modalidade += "painel_bedin"
    elif com_bedin:
        modalidade += "inversor_bedin"
    else:
        modalidade += "inversor_outros"
    
    return {
        "modalidade": modalidade,
        "tipo_equipamento": tipo_equipamento,
        "num_visitas": num_visitas,
        "num_tecnicos": num_tecnicos,
        "horas_por_visita": horas_por_visita,
        "valor_por_visita": visita["total"],
        "total_visitas": total_visitas,
        "deslocamento_bedin": total_bedin,
        "total": total,
        "detalhes_visita": visita,
        "detalhamento": detalhamento,
        "observacao": f"Período médio de garantia: 60 dias. {tipo_equipamento.capitalize()} será recolhido."
    }


def calcular_levantamento_sinistro(distancia_km, horas, valor_hora_override=None):
    """Levantamento de Danos do Sinistro (1 técnico)."""
    resultado = calcular_assistencia_paga(distancia_km, 1, horas, valor_hora_override)
    resultado["modalidade"] = "levantamento_sinistro"
    resultado["observacao"] = "Levantamento sempre realizado por 1 técnico"
    return resultado


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def calcular_modalidade(modalidade, distancia_km, num_tecnicos=1, horas=1.0, potencia_kwp=0.0, valor_hora_override=None, valor_deslocamento_override=None):
    """Função principal de roteamento."""
    
    if modalidade == 'garantia_painel_bedin':
        num_tecnicos = 2
    if modalidade == 'levantamento_sinistro':
        num_tecnicos = 1
    
    if modalidade == 'assistencia_paga':
        return calcular_assistencia_paga(distancia_km, num_tecnicos, horas, valor_hora_override, valor_deslocamento_override)
    
    elif modalidade == 'garantia_instalacao':
        return calcular_garantia_instalacao(distancia_km, num_tecnicos, horas)
    
    elif modalidade in ['ajuste_monitoramento', 'troca_dps']:
        return calcular_servico_fixo(distancia_km, modalidade)
    
    elif modalidade == 'garantia_inversor_outros':
        return calcular_garantia_inversor(distancia_km, num_tecnicos, horas, com_bedin=False, tipo_equipamento="inversor", valor_hora_override=valor_hora_override)
    
    elif modalidade == 'garantia_inversor_bedin':
        return calcular_garantia_inversor(distancia_km, num_tecnicos, horas, com_bedin=True, tipo_equipamento="inversor", valor_hora_override=valor_hora_override)
    
    elif modalidade == 'garantia_painel_bedin':
        return calcular_garantia_inversor(distancia_km, num_tecnicos, horas, com_bedin=True, tipo_equipamento="painel", valor_hora_override=valor_hora_override)
    
    elif modalidade == 'levantamento_sinistro':
        return calcular_levantamento_sinistro(distancia_km, horas, valor_hora_override)
    
    else:
        # Se modalidade não for hardcoded, verificar se existe no banco como ConfigCustom?
        # Por enquanto, mantemos erro ou fallback para assistencia_paga
        try:
            # Fallback seguro
            return calcular_assistencia_paga(distancia_km, num_tecnicos, horas, valor_hora_override, valor_deslocamento_override)
        except:
             raise ValueError(f"Modalidade desconhecida: {modalidade}")
