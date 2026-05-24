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