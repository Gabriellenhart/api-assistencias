from datetime import date, datetime, timedelta

from api.services.briefing_service import (
    calcular_score,
    classificar_status_prazo,
    normalizar_texto,
    prazo_label,
    prioridade_original_normalizada,
    prioridade_por_score,
    status_finalizado,
    sugerir_proxima_acao,
    truncar_texto,
    gerar_briefing_diario,
    montar_ultima_acao_detalhada,
)


def test_normalizar_texto_remove_acentos():
    assert normalizar_texto("Concluído") == "concluido"
    assert normalizar_texto(" CRÍTICA ") == "critica"
    assert normalizar_texto(None) == ""


def test_status_finalizado():
    assert status_finalizado("Resolvido") is True
    assert status_finalizado("concluído") is True
    assert status_finalizado("Cancelado") is True
    assert status_finalizado("Aberto") is False
    assert status_finalizado(None) is False


def test_classificar_status_prazo():
    hoje = date(2026, 5, 24)

    assert classificar_status_prazo(None, hoje) == "sem_prazo"
    assert classificar_status_prazo(hoje - timedelta(days=1), hoje) == "atrasado"
    assert classificar_status_prazo(hoje, hoje) == "vence_hoje"
    assert classificar_status_prazo(hoje + timedelta(days=1), hoje) == "vence_amanha"
    assert classificar_status_prazo(hoje + timedelta(days=2), hoje) == "futuro"


def test_classificar_status_prazo_aceita_datetime():
    hoje = datetime(2026, 5, 24, 10, 30)
    prazo = datetime(2026, 5, 24, 17, 0)

    assert classificar_status_prazo(prazo, hoje) == "vence_hoje"


def test_prioridade_por_score():
    assert prioridade_por_score(90) == "critica"
    assert prioridade_por_score(70) == "alta"
    assert prioridade_por_score(40) == "media"
    assert prioridade_por_score(10) == "baixa"


def test_truncar_texto():
    assert truncar_texto("texto curto", 20) == "texto curto"

    texto_longo = "a" * 100
    resultado = truncar_texto(texto_longo, 20)

    assert len(resultado) <= 20
    assert resultado.endswith("...")


def test_calcular_score_maximo_100():
    score = calcular_score(
        status_prazo="atrasado",
        prioridade_original="crítica",
        sem_responsavel=True,
        sem_prazo=True,
        dias_sem_atualizacao=5,
        aguardando_cliente=True,
    )

    assert score == 100


def test_calcular_score_prioridade_alta():
    score = calcular_score(
        status_prazo="vence_hoje",
        prioridade_original="alta",
        sem_responsavel=False,
        sem_prazo=False,
        dias_sem_atualizacao=0,
        aguardando_cliente=False,
    )

    assert score == 50


def test_sugerir_proxima_acao():
    assert (
        sugerir_proxima_acao("sem_prazo", sem_responsavel=True)
        == "Definir responsável pelo atendimento."
    )

    assert (
        sugerir_proxima_acao("atrasado")
        == "Revisar urgência, atualizar o cliente e registrar plano de ação."
    )

    assert (
        sugerir_proxima_acao("sem_prazo", sem_prazo=True)
        == "Definir prazo e próxima etapa do atendimento."
    )


def test_prioridade_original_normalizada():
    assert prioridade_original_normalizada("Crítica") == "critica"
    assert prioridade_original_normalizada("ALTA") == "alta"
    assert prioridade_original_normalizada("Média") == "media"
    assert prioridade_original_normalizada(None) == "baixa"


def test_prazo_label():
    hoje = date(2026, 5, 24)

    assert prazo_label(None, "sem_prazo") == "Sem prazo"
    assert prazo_label(hoje, "vence_hoje") == "Vence hoje"
    assert prazo_label(hoje, "vence_amanha") == "Vence amanhã"
    assert prazo_label(hoje, "atrasado") == "Atrasado"
    assert prazo_label(hoje + timedelta(days=3), "futuro") == "2026-05-27"

def test_gerar_briefing_diario_escopo_invalido():
    try:
        gerar_briefing_diario(escopo="orcamentos")
        assert False, "Deveria levantar ValueError para escopo inválido"
    except ValueError as exc:
        assert "Escopo ainda não suportado" in str(exc)


def test_gerar_briefing_diario_retorna_estrutura(app):
    with app.app_context():
        resultado = gerar_briefing_diario(limite=5)

    assert isinstance(resultado, dict)
    assert "data_referencia" in resultado
    assert "gerado_em" in resultado
    assert resultado["escopo"] == "chamados"
    assert "resumo" in resultado
    assert "tarefas" in resultado
    assert isinstance(resultado["tarefas"], list)


def test_gerar_briefing_diario_resumo_tem_chaves(app):
    with app.app_context():
        resultado = gerar_briefing_diario(limite=5)

    resumo = resultado["resumo"]

    chaves = {
        "total",
        "criticos",
        "altos",
        "medios",
        "baixos",
        "atrasados",
        "vencem_hoje",
        "vencem_amanha",
        "sem_prazo",
        "sem_responsavel",
        "sem_atualizacao",
        "aguardando_cliente",
    }

    assert chaves.issubset(set(resumo.keys()))


def test_gerar_briefing_diario_limite(app):
    with app.app_context():
        resultado = gerar_briefing_diario(limite=1)

    assert len(resultado["tarefas"]) <= 1

def test_resolver_id_chamado_prefere_id_chamado():
    from api.services.briefing_service import _resolver_id_chamado

    class ChamadoFake:
        id_chamado = 123
        id = None

    chamado = ChamadoFake()

    assert _resolver_id_chamado(chamado) == 123


def test_resolver_id_chamado_usa_id_como_fallback():
    from api.services.briefing_service import _resolver_id_chamado

    class ChamadoFake:
        id = 456

    chamado = ChamadoFake()

    assert _resolver_id_chamado(chamado) == 456


def test_resolver_id_chamado_retorna_none_quando_nao_existe():
    from api.services.briefing_service import _resolver_id_chamado

    class ChamadoFake:
        pass

    chamado = ChamadoFake()

    assert _resolver_id_chamado(chamado) is None

def test_ultima_acao_log_automatico_nao_retorna_automatico():
    class LogFake:
        tipo_log = "automatico"
        data_criacao = datetime(2026, 5, 23, 15, 40)

    class ChamadoFake:
        status = "Aguardando Fabricante"
        logs = [LogFake()]

    resultado = montar_ultima_acao_detalhada(ChamadoFake())

    assert resultado["texto"] != "automatico"
    assert "Status atual: Aguardando Fabricante" in resultado["texto"]
    assert resultado["usuario"] == "Sistema"


def test_ultima_acao_alteracao_status_com_usuario_e_data():
    class UsuarioFake:
        nome_usuario = "Gabriel"

    class LogFake:
        campo = "status"
        valor_anterior = "Em análise"
        valor_novo = "Aguardando Fabricante"
        usuario = UsuarioFake()
        data_criacao = datetime(2026, 5, 23, 15, 40)

    class ChamadoFake:
        status = "Aguardando Fabricante"
        logs = [LogFake()]

    resultado = montar_ultima_acao_detalhada(ChamadoFake())

    assert resultado["tipo"] == "alteracao_status"
    assert resultado["origem"] == "auditoria"
    assert resultado["usuario"] == "Gabriel"
    assert resultado["data"] == "2026-05-23T15:40:00"
    assert (
        resultado["texto"]
        == "Status alterado de Em análise para Aguardando Fabricante por Gabriel em 23/05/2026 15:40."
    )
    assert resultado["detalhes"]["campo"] == "status"
    assert resultado["detalhes"]["valor_anterior"] == "Em análise"
    assert resultado["detalhes"]["valor_novo"] == "Aguardando Fabricante"


def test_ultima_acao_status_com_apenas_valor_novo():
    class UsuarioFake:
        nome_usuario = "Técnico"

    class LogFake:
        campo_alterado = "status"
        valor_novo = "Aguardando Pagamento"
        usuario = UsuarioFake()
        data_criacao = datetime(2026, 5, 23, 10, 15)

    class ChamadoFake:
        status = "Aguardando Pagamento"
        logs = [LogFake()]

    resultado = montar_ultima_acao_detalhada(ChamadoFake())

    assert resultado["tipo"] == "alteracao_status"
    assert (
        resultado["texto"]
        == "Status alterado para Aguardando Pagamento por Técnico em 23/05/2026 10:15."
    )


def test_ultima_acao_comentario_com_usuario_e_data():
    class UsuarioFake:
        nome_usuario = "Maria"

    class ComentarioFake:
        id = 55
        comentario = "Cliente informou que o inversor voltou a apresentar falha."
        usuario = UsuarioFake()
        data_criacao = datetime(2026, 5, 23, 16, 20)

    class ChamadoFake:
        status = "Em andamento"
        comentarios = [ComentarioFake()]
        logs = []

    resultado = montar_ultima_acao_detalhada(ChamadoFake())

    assert resultado["tipo"] == "comentario"
    assert resultado["origem"] == "comentario"
    assert resultado["usuario"] == "Maria"
    assert resultado["data"] == "2026-05-23T16:20:00"
    assert resultado["texto"].startswith("Comentário por Maria em 23/05/2026 16:20:")
    assert resultado["detalhes"]["comentario_id"] == 55


def test_ultima_acao_comentario_mais_recente_vence_log():
    class LogFake:
        campo = "status"
        valor_novo = "Em análise"
        data_criacao = datetime(2026, 5, 22, 10, 0)

    class ComentarioFake:
        comentario = "Comentário mais recente."
        autor = "Gabriel"
        data_criacao = datetime(2026, 5, 23, 10, 0)

    class ChamadoFake:
        status = "Em análise"
        logs = [LogFake()]
        comentarios = [ComentarioFake()]

    resultado = montar_ultima_acao_detalhada(ChamadoFake())

    assert resultado["tipo"] == "comentario"
    assert "Comentário mais recente" in resultado["texto"]


def test_ultima_acao_log_mais_recente_vence_comentario():
    class LogFake:
        campo = "status"
        valor_novo = "Aguardando Fabricante"
        autor = "Sistema"
        data_criacao = datetime(2026, 5, 24, 10, 0)

    class ComentarioFake:
        comentario = "Comentário antigo."
        autor = "Gabriel"
        data_criacao = datetime(2026, 5, 23, 10, 0)

    class ChamadoFake:
        status = "Aguardando Fabricante"
        logs = [LogFake()]
        comentarios = [ComentarioFake()]

    resultado = montar_ultima_acao_detalhada(ChamadoFake())

    assert resultado["tipo"] == "alteracao_status"
    assert "Aguardando Fabricante" in resultado["texto"]


def test_ultima_acao_fallback_sem_log_e_sem_comentario():
    class ChamadoFake:
        status = "Aberto"

    resultado = montar_ultima_acao_detalhada(ChamadoFake())

    assert resultado["tipo"] == "fallback"
    assert resultado["origem"] == "chamado"
    assert resultado["usuario"] == "Sistema"
    assert resultado["texto"] == "Status atual: Aberto."