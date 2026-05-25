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

def _importar_model_por_nomes(possibilidades: tuple[tuple[str, str], ...]):
    """
    Importa dinamicamente um model tentando diferentes módulos/classes.
    Retorna a classe encontrada ou None.
    """
    for modulo, classe in possibilidades:
        try:
            module = __import__(modulo, fromlist=[classe])
            model = getattr(module, classe, None)
            if model is not None:
                return model
        except Exception:
            continue

    return None


def _model_log_chamado():
    return _importar_model_por_nomes(
        (
            ("api.models.chamado_log", "ChamadoLog"),
            ("api.models.chamado_logs", "ChamadoLog"),
            ("api.models.log_chamado", "ChamadoLog"),
            ("api.models.logs_chamado", "ChamadoLog"),
            ("api.models.chamado", "ChamadoLog"),
            ("api.models", "ChamadoLog"),
        )
    )


def _model_comentario_chamado():
    return _importar_model_por_nomes(
        (
            ("api.models.chamado_comentario", "ChamadoComentario"),
            ("api.models.chamado_comentarios", "ChamadoComentario"),
            ("api.models.comentario_chamado", "ChamadoComentario"),
            ("api.models.comentarios_chamado", "ChamadoComentario"),
            ("api.models.comentario", "Comentario"),
            ("api.models.comentarios", "Comentario"),
            ("api.models.chamado", "ChamadoComentario"),
            ("api.models", "ChamadoComentario"),
            ("api.models", "Comentario"),
        )
    )


def _campo_existente_model(model: Any, nomes: tuple[str, ...]) -> str | None:
    if model is None:
        return None

    for nome in nomes:
        if hasattr(model, nome):
            return nome

    return None


def _buscar_ultimo_por_query(
    model: Any,
    id_chamado: int | None,
    campos_fk: tuple[str, ...],
) -> Any:
    """
    Busca último registro relacionado ao chamado diretamente no banco.
    Usado quando o objeto Chamado não carrega logs/comentários como relação.
    """
    if model is None or id_chamado is None:
        return None

    campo_fk = _campo_existente_model(model, campos_fk)
    if campo_fk is None:
        return None

    try:
        query = model.query.filter(getattr(model, campo_fk) == id_chamado)
    except Exception:
        return None

    campos_data = (
        "data_criacao",
        "created_at",
        "criado_em",
        "data",
        "timestamp",
        "updated_at",
        "atualizado_em",
    )

    campo_data = _campo_existente_model(model, campos_data)

    try:
        if campo_data:
            return query.order_by(getattr(model, campo_data).desc()).first()

        campo_id = _campo_existente_model(
            model,
            (
                "id",
                "id_log",
                "id_comentario",
                "id_chamado_log",
                "id_chamado_comentario",
            ),
        )

        if campo_id:
            return query.order_by(getattr(model, campo_id).desc()).first()

        return query.first()

    except Exception:
        return None


def _buscar_ultimo_log_por_id_chamado(id_chamado: int | None) -> Any:
    model = _model_log_chamado()

    return _buscar_ultimo_por_query(
        model,
        id_chamado,
        (
            "id_chamado",
            "chamado_id",
            "id_chamado_fk",
        ),
    )


def _buscar_ultimo_comentario_por_id_chamado(id_chamado: int | None) -> Any:
    model = _model_comentario_chamado()

    return _buscar_ultimo_por_query(
        model,
        id_chamado,
        (
            "id_chamado",
            "chamado_id",
            "id_chamado_fk",
        ),
    )

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
    """
    Retorna uma data usada apenas para ordenação.
    Prazos ausentes vão para o final da lista.
    """
    prazo_data = apenas_data(prazo)

    if prazo_data is None:
        return date.max

    return prazo_data

def _resolver_datetime(valor: Any) -> datetime | None:
    """
    Normaliza datas de eventos para datetime, permitindo comparação entre
    logs, comentários e auditoria.
    """
    if valor is None:
        return None

    if isinstance(valor, datetime):
        return valor

    if isinstance(valor, date):
        return datetime.combine(valor, datetime.min.time())

    return None


def _resolver_data_evento(evento: Any) -> datetime | None:
    """
    Resolve a data/hora de um evento de comentário, log ou auditoria.
    """
    valor = _getattr_any(
        evento,
        (
            "data_criacao",
            "created_at",
            "criado_em",
            "data",
            "timestamp",
            "updated_at",
            "atualizado_em",
        ),
        None,
    )

    return _resolver_datetime(valor)


def _data_evento_iso(data_evento: datetime | None) -> str | None:
    if data_evento is None:
        return None

    return data_evento.isoformat(timespec="seconds")


def _formatar_data_evento(data_evento: datetime | None) -> str | None:
    """
    Formata data para texto operacional.
    """
    if data_evento is None:
        return None

    return data_evento.strftime("%d/%m/%Y %H:%M")


def _resolver_nome_usuario_de_objeto(usuario_obj: Any) -> str | None:
    """
    Resolve o nome do usuário a partir de uma relação/objeto de usuário.
    """
    if usuario_obj is None:
        return None

    nome = _getattr_any(
        usuario_obj,
        (
            "nome_usuario",
            "nome",
            "name",
            "email",
            "username",
            "login",
        ),
        None,
    )

    if nome:
        return truncar_texto(nome, 80)

    return None


def _resolver_usuario_evento(evento: Any) -> str:
    """
    Resolve o usuário responsável pelo evento.

    Tenta primeiro relações de usuário, depois campos textuais, depois IDs.
    Se nada existir, retorna Sistema.
    """
    for relacao in (
        "usuario",
        "user",
        "autor_usuario",
        "criado_por_usuario",
        "responsavel",
    ):
        usuario_obj = getattr(evento, relacao, None)
        nome = _resolver_nome_usuario_de_objeto(usuario_obj)
        if nome:
            return nome

    nome_direto = _getattr_any(
        evento,
        (
            "nome_usuario",
            "usuario_nome",
            "autor",
            "criado_por",
            "email_usuario",
            "usuario_email",
        ),
        None,
    )

    if nome_direto:
        return truncar_texto(nome_direto, 80)

    usuario_id = _getattr_any(
        evento,
        (
            "usuario_id",
            "id_usuario",
            "criado_por_id",
            "autor_id",
        ),
        None,
    )

    if usuario_id not in (None, ""):
        return f"Usuário #{usuario_id}"

    return "Sistema"


def _texto_data_usuario(usuario: str | None, data_evento: datetime | None) -> str:
    """
    Monta trecho textual:
    - por Gabriel em 23/05/2026 15:40
    - por Gabriel
    - em 23/05/2026 15:40
    - ""
    """
    usuario_limpo = truncar_texto(usuario, 80) if usuario else ""
    data_formatada = _formatar_data_evento(data_evento)

    if usuario_limpo and data_formatada:
        return f"por {usuario_limpo} em {data_formatada}"

    if usuario_limpo:
        return f"por {usuario_limpo}"

    if data_formatada:
        return f"em {data_formatada}"

    return ""


def _texto_generico_automatico(texto: Any) -> bool:
    texto_normalizado = normalizar_texto(texto)

    return texto_normalizado in {
        "automatico",
        "auto",
        "sistema",
        "automatizado",
    }


def _resolver_primeiro_texto_util(evento: Any) -> str | None:
    """
    Busca um texto útil no evento, ignorando textos genéricos como automatico.
    """
    texto = _getattr_any(
        evento,
        (
            "comentario",
            "descricao",
            "mensagem",
            "texto",
            "conteudo",
            "detalhes",
            "acao",
            "tipo_log",
            "tipo",
        ),
        None,
    )

    if not texto:
        return None

    texto_curto = truncar_texto(texto, 180)

    if _texto_generico_automatico(texto_curto):
        return None

    return texto_curto


def _resolver_campo_alterado(evento: Any) -> str | None:
    campo = _getattr_any(
        evento,
        (
            "campo",
            "campo_alterado",
            "field",
            "atributo",
        ),
        None,
    )

    if campo:
        return truncar_texto(campo, 80)

    return None


def _resolver_valor_anterior(evento: Any) -> Any:
    return _getattr_any(
        evento,
        (
            "valor_anterior",
            "valor_antigo",
            "antes",
            "old_value",
            "valor_old",
        ),
        None,
    )


def _resolver_valor_novo(evento: Any) -> Any:
    return _getattr_any(
        evento,
        (
            "valor_novo",
            "novo_valor",
            "depois",
            "new_value",
            "valor_new",
            "status_novo",
            "status",
        ),
        None,
    )


def _evento_indica_status(evento: Any) -> bool:
    """
    Detecta se o evento parece ser alteração de status.
    """
    campo = normalizar_texto(_resolver_campo_alterado(evento))

    if campo == "status":
        return True

    texto_composto = " ".join(
        normalizar_texto(_getattr_any(evento, (campo_nome,), ""))
        for campo_nome in (
            "acao",
            "descricao",
            "mensagem",
            "texto",
            "tipo",
            "tipo_log",
            "campo",
            "campo_alterado",
        )
    )

    return "status" in texto_composto


def _evento_e_comentario(evento: Any) -> bool:
    """
    Detecta comentário pela presença de campos típicos.
    """
    texto = _getattr_any(
        evento,
        (
            "comentario",
            "conteudo",
            "texto",
        ),
        None,
    )

    if texto:
        return True

    tipo = normalizar_texto(_getattr_any(evento, ("tipo", "tipo_log", "origem"), ""))

    return "comentario" in tipo


def _formatar_comentario_evento(evento: Any) -> dict[str, Any]:
    data_evento = _resolver_data_evento(evento)
    usuario = _resolver_usuario_evento(evento)
    texto = _resolver_primeiro_texto_util(evento) or "Comentário registrado."

    trecho_usuario_data = _texto_data_usuario(usuario, data_evento)

    if trecho_usuario_data:
        texto_final = f"Comentário {trecho_usuario_data}: {texto}"
    else:
        texto_final = f"Comentário: {texto}"

    comentario_id = _getattr_any(evento, ("id", "id_comentario", "comentario_id"), None)

    return {
        "texto": truncar_texto(texto_final, 240),
        "tipo": "comentario",
        "origem": "comentario",
        "data": _data_evento_iso(data_evento),
        "usuario": usuario,
        "detalhes": {
            "comentario_id": comentario_id,
        },
    }


def _formatar_log_auditoria_evento(evento: Any, chamado: Any) -> dict[str, Any]:
    data_evento = _resolver_data_evento(evento)
    usuario = _resolver_usuario_evento(evento)
    trecho_usuario_data = _texto_data_usuario(usuario, data_evento)

    campo = _resolver_campo_alterado(evento)
    campo_normalizado = normalizar_texto(campo)

    valor_anterior = _resolver_valor_anterior(evento)
    valor_novo = _resolver_valor_novo(evento)

    status_atual = _getattr_any(chamado, ("status",), None)

    tipo = "auditoria"
    origem = "auditoria"

    if _evento_indica_status(evento) or campo_normalizado == "status":
        tipo = "alteracao_status"

        if valor_anterior and valor_novo:
            texto = f"Status alterado de {valor_anterior} para {valor_novo}"
        elif valor_novo:
            texto = f"Status alterado para {valor_novo}"
        elif status_atual:
            texto = f"Status atual: {status_atual}"
        else:
            texto = "Status do chamado atualizado"

        if trecho_usuario_data:
            texto = f"{texto} {trecho_usuario_data}."

        else:
            texto = f"{texto}."

        return {
            "texto": truncar_texto(texto, 240),
            "tipo": tipo,
            "origem": origem,
            "data": _data_evento_iso(data_evento),
            "usuario": usuario,
            "detalhes": {
                "campo": campo or "status",
                "valor_anterior": valor_anterior,
                "valor_novo": valor_novo,
            },
        }

    texto_util = _resolver_primeiro_texto_util(evento)

    if texto_util and not _texto_generico_automatico(texto_util):
        texto = texto_util

        if trecho_usuario_data:
            texto = f"{texto} {trecho_usuario_data}."

        return {
            "texto": truncar_texto(texto, 240),
            "tipo": tipo,
            "origem": origem,
            "data": _data_evento_iso(data_evento),
            "usuario": usuario,
            "detalhes": {
                "campo": campo,
                "valor_anterior": valor_anterior,
                "valor_novo": valor_novo,
            },
        }

    if status_atual:
        texto = f"Status atual: {status_atual}"

        if trecho_usuario_data:
            texto = f"{texto} {trecho_usuario_data}."
        else:
            texto = f"{texto}."

        return {
            "texto": truncar_texto(texto, 240),
            "tipo": "fallback",
            "origem": "auditoria",
            "data": _data_evento_iso(data_evento),
            "usuario": usuario,
            "detalhes": {
                "campo": campo,
                "valor_anterior": valor_anterior,
                "valor_novo": valor_novo,
            },
        }

    return {
        "texto": "Chamado criado e aguardando primeira análise.",
        "tipo": "fallback",
        "origem": "chamado",
        "data": _data_evento_iso(data_evento),
        "usuario": usuario,
        "detalhes": {},
    }


def _buscar_ultimo_item_relacionado(chamado: Any, nomes_relacao: tuple[str, ...]) -> Any:
    """
    Busca o item mais recente em relações como logs/comentários.

    Usa datas normalizadas para evitar erro de comparação entre date e datetime.
    """
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
            data_item = _resolver_data_evento(item) or datetime.min
            id_item = _getattr_any(item, ("id", "id_log", "id_comentario"), 0)
            return (data_item, id_item or 0)

        return sorted(itens, key=chave)[-1]

    return None


def _escolher_evento_mais_recente(comentario: Any, log: Any) -> tuple[Any | None, str | None]:
    if comentario is None and log is None:
        return None, None

    if comentario is not None and log is None:
        return comentario, "comentario"

    if log is not None and comentario is None:
        return log, "auditoria"

    data_comentario = _resolver_data_evento(comentario)
    data_log = _resolver_data_evento(log)

    if data_comentario is not None and data_log is not None:
        if data_comentario >= data_log:
            return comentario, "comentario"
        return log, "auditoria"

    if data_comentario is not None:
        return comentario, "comentario"

    if data_log is not None:
        return log, "auditoria"

    # Sem data clara, comentário é mais útil para o usuário.
    return comentario, "comentario"


def montar_ultima_acao_detalhada(
    chamado: Any,
    data_atualizacao: date | datetime | None = None,
) -> dict[str, Any]:
    """
    Monta a última ação operacional do chamado para o Briefing.

    Estratégia:
    1. Tenta usar relações já carregadas no objeto Chamado.
    2. Se não encontrar, consulta diretamente logs/comentários por id_chamado.
    3. Escolhe o evento mais recente.
    4. Formata texto útil com usuário e data.
    """
    id_chamado = _resolver_id_chamado(chamado)

    ultimo_comentario = _buscar_ultimo_item_relacionado(
        chamado,
        (
            "comentarios",
            "comentarios_chamado",
            "comments",
            "chamado_comentarios",
        ),
    )

    ultimo_log = _buscar_ultimo_item_relacionado(
        chamado,
        (
            "logs",
            "chamado_logs",
            "historicos",
            "historico",
            "auditorias",
            "auditoria",
        ),
    )

    # Fallback importante: buscar diretamente no banco por id_chamado.
    if ultimo_comentario is None:
        ultimo_comentario = _buscar_ultimo_comentario_por_id_chamado(id_chamado)

    if ultimo_log is None:
        ultimo_log = _buscar_ultimo_log_por_id_chamado(id_chamado)

    evento, origem = _escolher_evento_mais_recente(ultimo_comentario, ultimo_log)

    if evento is None:
        status = _getattr_any(chamado, ("status",), None)
        data_evento = _resolver_datetime(data_atualizacao)
        data_iso = _data_evento_iso(data_evento)

        if status:
            texto = f"Status atual: {status}."
        else:
            texto = "Chamado criado e aguardando primeira análise."

        return {
            "texto": texto,
            "tipo": "fallback",
            "origem": "chamado",
            "data": data_iso,
            "usuario": "Sistema",
            "detalhes": {},
        }

    if origem == "comentario" or _evento_e_comentario(evento):
        return _formatar_comentario_evento(evento)

    return _formatar_log_auditoria_evento(evento, chamado)


def montar_ultima_acao(
    chamado: Any,
    data_atualizacao: date | datetime | None = None,
) -> str:
    """
    Mantém compatibilidade com chamadas antigas que esperam apenas string.
    A lógica principal agora fica em montar_ultima_acao_detalhada().
    """
    return montar_ultima_acao_detalhada(chamado, data_atualizacao)["texto"]

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

def _resolver_id_chamado(chamado: Any) -> int | None:
    """
    Resolve o identificador real do chamado.

    O model principal de chamados pode usar `id_chamado` em vez de `id`.
    O briefing precisa retornar esse ID para o frontend abrir corretamente
    a tela de detalhes em #/chamados/:id.
    """
    id_chamado = _getattr_any(
        chamado,
        (
            "id_chamado",
            "chamado_id",
            "id",
        ),
        None,
    )

    if id_chamado is None:
        return None

    try:
        return int(id_chamado)
    except (TypeError, ValueError):
        return None


def _montar_tarefa_chamado(
    chamado: Any,
    data_referencia: date,
) -> dict[str, Any] | None:
    chamado_id = _resolver_id_chamado(chamado)
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
    ultima_acao_info = montar_ultima_acao_detalhada(chamado, data_atualizacao)

    return {
        "ordem": 0,
        "tipo": "chamado",
        "id": chamado_id,
        "id_chamado": chamado_id,
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
        "ultima_acao": ultima_acao_info["texto"],
        "ultima_acao_tipo": ultima_acao_info["tipo"],
        "ultima_acao_origem": ultima_acao_info["origem"],
        "ultima_acao_data": ultima_acao_info["data"],
        "ultima_acao_usuario": ultima_acao_info["usuario"],
        "ultima_acao_detalhes": ultima_acao_info["detalhes"],
        "proxima_acao": proxima_acao,
        "motivo": truncar_texto(", ".join(motivos), 180),
        "motivos": motivos,
        "dias_sem_atualizacao": dias_sem_atualizacao,
        "score": score,
        "url": f"/chamados/{chamado_id}" if chamado_id is not None else None,
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