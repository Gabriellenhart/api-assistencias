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


def _normalizar_limite(limite: Any) -> int:
    try:
        valor = int(limite)
    except (TypeError, ValueError):
        valor = 50

    if valor < 1:
        return 1

    if valor > 200:
        return 200

    return valor


def _normalizar_data_referencia(valor: Any) -> date:
    data = apenas_data(valor)
    if data is not None:
        return data
    return date.today()


def _get_chamado_model():
    """
    Importa o model Chamado de forma tardia para manter funções puras testáveis
    sem exigir app context no import do módulo.
    """
    tentativas = (
        "api.models.chamado",
        "api.models.chamados",
        "api.models",
    )

    ultimo_erro = None

    for modulo in tentativas:
        try:
            module = __import__(modulo, fromlist=["Chamado"])
            chamado_model = getattr(module, "Chamado", None)
            if chamado_model is not None:
                return chamado_model
        except Exception as exc:  # pragma: no cover - diagnóstico defensivo
            ultimo_erro = exc

    raise ImportError(f"Model Chamado não encontrado. Último erro: {ultimo_erro}")


def _getattr_any(obj: Any, nomes: tuple[str, ...], default: Any = None) -> Any:
    for nome in nomes:
        if hasattr(obj, nome):
            valor = getattr(obj, nome)
            if valor is not None:
                return valor
    return default


def _nome_relacionado(obj: Any, campos: tuple[str, ...]) -> str | None:
    if obj is None:
        return None

    for campo in campos:
        if hasattr(obj, campo):
            valor = getattr(obj, campo)
            if valor:
                return str(valor)

    return None


def _resolver_cliente(chamado: Any) -> str:
    cliente = _getattr_any(chamado, ("cliente", "cliente_obj"), None)

    nome = _nome_relacionado(
        cliente,
        (
            "nome",
            "nome_cliente",
            "razao_social",
            "nome_fantasia",
            "cliente",
        ),
    )

    if nome:
        return truncar_texto(nome, 80)

    nome_direto = _getattr_any(
        chamado,
        ("cliente_nome", "nome_cliente", "cliente"),
        None,
    )

    if nome_direto:
        return truncar_texto(nome_direto, 80)

    return "Não informado"


def _resolver_usina(chamado: Any) -> str:
    usina = _getattr_any(chamado, ("usina", "usina_obj"), None)

    nome = _nome_relacionado(
        usina,
        (
            "nome",
            "nome_usina",
            "denominacao",
            "apelido",
        ),
    )

    if nome:
        return truncar_texto(nome, 80)

    nome_direto = _getattr_any(
        chamado,
        ("usina_nome", "nome_usina"),
        None,
    )

    if nome_direto:
        return truncar_texto(nome_direto, 80)

    return "Não informada"


def _resolver_titulo(chamado: Any) -> str:
    titulo = _getattr_any(
        chamado,
        (
            "titulo",
            "assunto",
            "nome",
            "descricao_curta",
        ),
        None,
    )

    if titulo:
        return truncar_texto(titulo, 80)

    descricao = _getattr_any(chamado, ("descricao", "observacao", "observacoes"), None)
    if descricao:
        return truncar_texto(descricao, 80)

    return "Chamado sem título"


def _resolver_data_atualizacao(chamado: Any) -> date | None:
    valor = _getattr_any(
        chamado,
        (
            "data_atualizacao",
            "updated_at",
            "atualizado_em",
            "data_modificacao",
            "data_criacao",
            "created_at",
            "criado_em",
        ),
        None,
    )

    return apenas_data(valor)


def _resolver_prazo(chamado: Any) -> Any:
    return _getattr_any(
        chamado,
        (
            "data_agendamento",
            "data_limite",
            "prazo",
            "prazo_resolucao",
            "data_limite_resolucao",
        ),
        None,
    )


def _chamado_sem_responsavel(chamado: Any) -> bool:
    responsavel_id = _getattr_any(
        chamado,
        (
            "responsavel_id",
            "usuario_id",
            "tecnico_id",
            "atendente_id",
        ),
        None,
    )

    responsavel = _getattr_any(
        chamado,
        (
            "responsavel",
            "usuario",
            "tecnico",
            "atendente",
        ),
        None,
    )

    return responsavel_id is None and responsavel is None


def _dias_sem_atualizacao(
    data_atualizacao: date | None,
    data_referencia: date,
) -> int:
    if data_atualizacao is None:
        return 0

    dias = (data_referencia - data_atualizacao).days
    return max(dias, 0)


def _inferir_aguardando_cliente(chamado: Any) -> bool:
    status = normalizar_texto(_getattr_any(chamado, ("status",), ""))
    categoria = normalizar_texto(_getattr_any(chamado, ("categoria",), ""))
    texto = f"{status} {categoria}"

    return "aguardando" in texto and "cliente" in texto


def _valor_data_ordenacao(prazo: Any) -> date:
    prazo_data = apenas_data(prazo)
    if prazo_data is None:
        return date.max
    return prazo_data


def _buscar_ultimo_item_relacionado(chamado: Any, nomes_relacao: tuple[str, ...]) -> Any:
    for nome in nomes_relacao:
        if not hasattr(chamado, nome):
            continue

        relacao = getattr(chamado, nome)

        if relacao is None:
            continue

        try:
            itens = list(relacao)
        except TypeError:
            continue

        if not itens:
            continue

        def chave(item: Any):
            data_item = _getattr_any(
                item,
                (
                    "data_criacao",
                    "created_at",
                    "criado_em",
                    "data",
                    "timestamp",
                ),
                None,
            )
            id_item = _getattr_any(item, ("id",), 0)
            return (data_item or datetime.min, id_item or 0)

        return sorted(itens, key=chave)[-1]

    return None


def _texto_de_item_relacionado(item: Any) -> str | None:
    if item is None:
        return None

    texto = _getattr_any(
        item,
        (
            "comentario",
            "descricao",
            "mensagem",
            "texto",
            "conteudo",
            "tipo_log",
            "acao",
        ),
        None,
    )

    if texto:
        return truncar_texto(texto, 180)

    return None


def montar_ultima_acao(chamado: Any, data_atualizacao: date | None = None) -> str:
    """
    Monta um resumo curto da última ação do chamado.

    Tenta relações comuns de logs/comentários. Se não houver relação simples,
    usa fallback seguro.
    """
    item = _buscar_ultimo_item_relacionado(
        chamado,
        (
            "logs",
            "comentarios",
            "comments",
            "chamado_logs",
        ),
    )

    texto = _texto_de_item_relacionado(item)
    if texto:
        return texto

    status = _getattr_any(chamado, ("status",), None)
    if status and data_atualizacao:
        return f"Status atual: {status}. Última atualização em {data_atualizacao.isoformat()}."

    if status:
        return f"Status atual: {status}."

    return "Chamado criado e aguardando primeira análise."


def _motivos_da_tarefa(
    status_prazo: str,
    sem_responsavel: bool,
    sem_prazo: bool,
    dias_sem_atualizacao: int,
    aguardando_cliente: bool,
) -> list[str]:
    motivos: list[str] = []

    if status_prazo == "atrasado":
        motivos.append("atrasado")

    if status_prazo == "vence_hoje":
        motivos.append("vence hoje")

    if status_prazo == "vence_amanha":
        motivos.append("vence amanhã")

    if sem_prazo:
        motivos.append("sem prazo")

    if sem_responsavel:
        motivos.append("sem responsável")

    if dias_sem_atualizacao >= 2:
        motivos.append("sem atualização recente")

    if aguardando_cliente:
        motivos.append("aguardando cliente")

    if not motivos:
        motivos.append("pendente")

    return motivos


def _montar_tarefa_chamado(
    chamado: Any,
    data_referencia: date,
) -> dict[str, Any] | None:
    chamado_id = _getattr_any(chamado, ("id",), None)
    status = _getattr_any(chamado, ("status",), "aberto")

    if status_finalizado(status):
        return None

    titulo = _resolver_titulo(chamado)
    cliente = _resolver_cliente(chamado)
    usina = _resolver_usina(chamado)
    prioridade_original = _getattr_any(chamado, ("prioridade",), "baixa")
    prioridade_original_norm = prioridade_original_normalizada(prioridade_original)

    prazo = _resolver_prazo(chamado)
    status_prazo = classificar_status_prazo(prazo, data_referencia)
    sem_prazo = status_prazo == "sem_prazo"
    sem_responsavel = _chamado_sem_responsavel(chamado)

    data_atualizacao = _resolver_data_atualizacao(chamado)
    dias_sem_atualizacao = _dias_sem_atualizacao(data_atualizacao, data_referencia)

    aguardando_cliente = _inferir_aguardando_cliente(chamado)

    score = calcular_score(
        status_prazo=status_prazo,
        prioridade_original=prioridade_original_norm,
        sem_responsavel=sem_responsavel,
        sem_prazo=sem_prazo,
        dias_sem_atualizacao=dias_sem_atualizacao,
        aguardando_cliente=aguardando_cliente,
    )

    prioridade = prioridade_por_score(score)

    motivos = _motivos_da_tarefa(
        status_prazo=status_prazo,
        sem_responsavel=sem_responsavel,
        sem_prazo=sem_prazo,
        dias_sem_atualizacao=dias_sem_atualizacao,
        aguardando_cliente=aguardando_cliente,
    )

    proxima_acao = sugerir_proxima_acao(
        status_prazo=status_prazo,
        sem_responsavel=sem_responsavel,
        sem_prazo=sem_prazo,
        dias_sem_atualizacao=dias_sem_atualizacao,
        aguardando_cliente=aguardando_cliente,
    )

    prazo_data = apenas_data(prazo)

    return {
        "ordem": 0,
        "tipo": "chamado",
        "id": chamado_id,
        "codigo": f"CH-{chamado_id}" if chamado_id is not None else "CH-S/I",
        "titulo": titulo,
        "cliente": cliente,
        "usina": usina,
        "status": status,
        "status_operacional": status_prazo,
        "prioridade_original": prioridade_original_norm,
        "prioridade": prioridade,
        "prazo": prazo_data.isoformat() if prazo_data is not None else None,
        "prazo_label": prazo_label(prazo, status_prazo),
        "status_prazo": status_prazo,
        "ultima_acao": montar_ultima_acao(chamado, data_atualizacao),
        "proxima_acao": proxima_acao,
        "motivo": truncar_texto(", ".join(motivos), 180),
        "motivos": motivos,
        "dias_sem_atualizacao": dias_sem_atualizacao,
        "score": score,
        "url": f"/chamados/{chamado_id}" if chamado_id is not None else "/chamados",
        "_ordem_prazo": _valor_data_ordenacao(prazo),
    }


def _montar_resumo(tarefas: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(tarefas),
        "criticos": sum(1 for item in tarefas if item["prioridade"] == "critica"),
        "altos": sum(1 for item in tarefas if item["prioridade"] == "alta"),
        "medios": sum(1 for item in tarefas if item["prioridade"] == "media"),
        "baixos": sum(1 for item in tarefas if item["prioridade"] == "baixa"),
        "atrasados": sum(1 for item in tarefas if item["status_prazo"] == "atrasado"),
        "vencem_hoje": sum(1 for item in tarefas if item["status_prazo"] == "vence_hoje"),
        "vencem_amanha": sum(1 for item in tarefas if item["status_prazo"] == "vence_amanha"),
        "sem_prazo": sum(1 for item in tarefas if item["status_prazo"] == "sem_prazo"),
        "sem_responsavel": sum(
            1 for item in tarefas if "sem responsável" in item["motivos"]
        ),
        "sem_atualizacao": sum(
            1 for item in tarefas if "sem atualização recente" in item["motivos"]
        ),
        "aguardando_cliente": sum(
            1 for item in tarefas if "aguardando cliente" in item["motivos"]
        ),
    }


def _limpar_campos_internos(tarefa: dict[str, Any]) -> dict[str, Any]:
    tarefa.pop("_ordem_prazo", None)
    return tarefa


def gerar_briefing_diario(
    data_referencia: date | datetime | None = None,
    escopo: str = "chamados",
    responsavel_id: Any = None,
    limite: Any = 50,
) -> dict[str, Any]:
    """
    Gera o Briefing Operacional Diário.

    MVP:
    - somente chamados;
    - somente leitura;
    - sem persistência;
    - sem migrations;
    - sem alteração de schema.
    """
    escopo_normalizado = normalizar_texto(escopo or "chamados")
    if escopo_normalizado != "chamados":
        raise ValueError("Escopo ainda não suportado no MVP.")

    data_ref = _normalizar_data_referencia(data_referencia)
    limite_normalizado = _normalizar_limite(limite)

    Chamado = _get_chamado_model()

    query = Chamado.query

    if responsavel_id not in (None, ""):
        for campo_responsavel in ("responsavel_id", "usuario_id", "tecnico_id", "atendente_id"):
            if hasattr(Chamado, campo_responsavel):
                try:
                    query = query.filter(getattr(Chamado, campo_responsavel) == int(responsavel_id))
                except (TypeError, ValueError):
                    pass
                break

    try:
        chamados = query.all()
    except Exception:
        chamados = []

    tarefas: list[dict[str, Any]] = []

    for chamado in chamados:
        tarefa = _montar_tarefa_chamado(chamado, data_ref)
        if tarefa is not None:
            tarefas.append(tarefa)

    tarefas.sort(
        key=lambda item: (
            -int(item.get("score") or 0),
            item.get("_ordem_prazo") or date.max,
            -int(item.get("dias_sem_atualizacao") or 0),
            -int(item.get("id") or 0),
        )
    )

    tarefas = tarefas[:limite_normalizado]

    for index, tarefa in enumerate(tarefas, start=1):
        tarefa["ordem"] = index
        _limpar_campos_internos(tarefa)

    resumo = _montar_resumo(tarefas)

    return {
        "data_referencia": data_ref.isoformat(),
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "escopo": "chamados",
        "resumo": resumo,
        "tarefas": tarefas,
    }