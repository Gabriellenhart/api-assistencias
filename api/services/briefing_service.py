from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any


STATUS_FINALIZADOS = {
    "resolvido",
    "concluido",
    "cancelado",
    "fechado",
    "finalizado",
}


def normalizar_texto(valor: Any) -> str:
    """
    Normaliza texto para comparações operacionais:
    - trata None como string vazia;
    - converte para minúsculas;
    - remove acentos;
    - remove espaços extras nas pontas.
    """
    if valor is None:
        return ""

    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")
    return texto


def status_finalizado(status: Any) -> bool:
    """
    Retorna True quando o status representa um chamado encerrado.
    A comparação ignora maiúsculas/minúsculas e acentos.
    """
    status_normalizado = normalizar_texto(status)
    return status_normalizado in STATUS_FINALIZADOS


def apenas_data(valor: Any) -> date | None:
    """
    Converte datetime/date para date.
    Valores desconhecidos retornam None.
    """
    if valor is None:
        return None

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, date):
        return valor

    return None


def classificar_status_prazo(
    prazo: Any,
    data_referencia: date | datetime | None = None,
) -> str:
    """
    Classifica prazo em:
    - sem_prazo
    - atrasado
    - vence_hoje
    - vence_amanha
    - futuro
    """
    prazo_data = apenas_data(prazo)

    referencia = apenas_data(data_referencia)
    if referencia is None:
        referencia = date.today()

    if prazo_data is None:
        return "sem_prazo"

    if prazo_data < referencia:
        return "atrasado"

    if prazo_data == referencia:
        return "vence_hoje"

    if prazo_data == referencia + timedelta(days=1):
        return "vence_amanha"

    return "futuro"


def prioridade_por_score(score: int) -> str:
    """
    Converte score numérico em prioridade operacional.
    """
    try:
        score_int = int(score)
    except (TypeError, ValueError):
        score_int = 0

    if score_int >= 80:
        return "critica"

    if score_int >= 60:
        return "alta"

    if score_int >= 30:
        return "media"

    return "baixa"


def truncar_texto(texto: Any, limite: int = 180) -> str:
    """
    Limita texto para uso em cards/listagens resumidas.
    """
    if texto is None:
        return ""

    try:
        limite_int = int(limite)
    except (TypeError, ValueError):
        limite_int = 180

    if limite_int <= 3:
        limite_int = 3

    texto_limpo = str(texto).replace("\n", " ").replace("\r", " ")
    texto_limpo = re.sub(r"\s+", " ", texto_limpo).strip()

    if len(texto_limpo) <= limite_int:
        return texto_limpo

    return texto_limpo[: limite_int - 3].rstrip() + "..."


def prioridade_original_normalizada(valor: Any) -> str:
    """
    Normaliza prioridade original do chamado para baixa/media/alta/critica.
    """
    prioridade = normalizar_texto(valor)

    if not prioridade:
        return "baixa"

    if "critica" in prioridade:
        return "critica"

    if "alta" in prioridade:
        return "alta"

    if "media" in prioridade:
        return "media"

    if "baixa" in prioridade:
        return "baixa"

    return prioridade


def calcular_score(
    status_prazo: str,
    prioridade_original: Any = None,
    sem_responsavel: bool = False,
    sem_prazo: bool = False,
    dias_sem_atualizacao: int = 0,
    aguardando_cliente: bool = False,
) -> int:
    """
    Calcula score operacional de uma tarefa/chamado.

    Regras:
    - +50 se atrasado
    - +35 se prioridade original crítica
    - +25 se prioridade original alta
    - +25 se vence hoje
    - +15 se vence amanhã
    - +20 se sem responsável
    - +15 se sem prazo
    - +15 se sem atualização há 2 dias ou mais
    - +10 se aguardando cliente
    - máximo 100
    """
    score = 0
    status_prazo_normalizado = normalizar_texto(status_prazo)
    prioridade = prioridade_original_normalizada(prioridade_original)

    if status_prazo_normalizado == "atrasado":
        score += 50

    if prioridade == "critica":
        score += 35
    elif prioridade == "alta":
        score += 25

    if status_prazo_normalizado == "vence_hoje":
        score += 25

    if status_prazo_normalizado == "vence_amanha":
        score += 15

    if sem_responsavel:
        score += 20

    if sem_prazo:
        score += 15

    try:
        dias = int(dias_sem_atualizacao or 0)
    except (TypeError, ValueError):
        dias = 0

    if dias >= 2:
        score += 15

    if aguardando_cliente:
        score += 10

    return min(score, 100)


def prazo_label(prazo: Any, status_prazo: str) -> str:
    """
    Gera label curto para exibição do prazo.
    """
    status = normalizar_texto(status_prazo)
    prazo_data = apenas_data(prazo)

    if status == "sem_prazo":
        return "Sem prazo"

    if status == "atrasado":
        return "Atrasado"

    if status == "vence_hoje":
        return "Vence hoje"

    if status == "vence_amanha":
        return "Vence amanhã"

    if prazo_data is not None:
        return prazo_data.isoformat()

    return "Sem prazo"


def sugerir_proxima_acao(
    status_prazo: str,
    sem_responsavel: bool = False,
    sem_prazo: bool = False,
    dias_sem_atualizacao: int = 0,
    aguardando_cliente: bool = False,
) -> str:
    """
    Sugere a próxima ação operacional do chamado com base em regras simples.
    """
    status = normalizar_texto(status_prazo)

    if sem_responsavel:
        return "Definir responsável pelo atendimento."

    if status == "atrasado":
        return "Revisar urgência, atualizar o cliente e registrar plano de ação."

    if status == "vence_hoje":
        return "Resolver ou posicionar o cliente ainda hoje."

    if sem_prazo:
        return "Definir prazo e próxima etapa do atendimento."

    if aguardando_cliente:
        return "Cobrar retorno do cliente."

    try:
        dias = int(dias_sem_atualizacao or 0)
    except (TypeError, ValueError):
        dias = 0

    if dias >= 2:
        return "Revisar andamento e registrar uma atualização."

    return "Revisar chamado e confirmar próxima ação."