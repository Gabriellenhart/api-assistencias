import uuid

from flask_jwt_extended import create_access_token

from api import db, bcrypt
from api.models.usuario import Usuario


def _criar_usuario_teste(app):
    """
    Cria um usuário real no banco de teste para que o user_lookup_loader
    consiga localizar o identity do JWT.

    Model real:
    - id_usuario
    - nome_usuario
    - email
    - password_hash
    - nivel
    """
    with app.app_context():
        identificador = uuid.uuid4().hex
        email = f"briefing_{identificador}@teste.local"

        usuario = Usuario(
            nome_usuario="Usuário Briefing Teste",
            email=email,
            password_hash=bcrypt.generate_password_hash("senha-teste").decode("utf-8"),
            nivel="admin",
        )

        db.session.add(usuario)
        db.session.commit()

        return usuario.id_usuario


def _auth_headers(app):
    user_id = _criar_usuario_teste(app)

    with app.app_context():
        token = create_access_token(identity=str(user_id))

    return {"Authorization": f"Bearer {token}"}


def test_briefing_diario_sem_auth(client):
    response = client.get("/briefing/diario")

    assert response.status_code in (401, 422)


def test_briefing_diario_com_auth(client, app):
    response = client.get(
        "/briefing/diario",
        headers=_auth_headers(app),
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert "data_referencia" in payload
    assert "gerado_em" in payload
    assert payload["escopo"] == "chamados"
    assert "resumo" in payload
    assert "tarefas" in payload
    assert isinstance(payload["tarefas"], list)


def test_briefing_diario_escopo_invalido(client, app):
    response = client.get(
        "/briefing/diario?escopo=orcamentos",
        headers=_auth_headers(app),
    )

    assert response.status_code == 400

    payload = response.get_json()
    assert "erro" in payload


def test_briefing_diario_data_invalida(client, app):
    response = client.get(
        "/briefing/diario?data=2026-99-99",
        headers=_auth_headers(app),
    )

    assert response.status_code == 400

    payload = response.get_json()
    assert "erro" in payload


def test_briefing_diario_limite(client, app):
    response = client.get(
        "/briefing/diario?limite=1",
        headers=_auth_headers(app),
    )

    assert response.status_code == 200

    payload = response.get_json()
    assert len(payload["tarefas"]) <= 1


def test_briefing_diario_limite_maximo(client, app):
    response = client.get(
        "/briefing/diario?limite=999",
        headers=_auth_headers(app),
    )

    assert response.status_code == 200

    payload = response.get_json()
    assert len(payload["tarefas"]) <= 200