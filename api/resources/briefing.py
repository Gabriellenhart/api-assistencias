from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from api.services.briefing_service import gerar_briefing_diario


briefing_bp = Blueprint("briefing", __name__)


def _parse_data_referencia(valor: str | None):
    if not valor:
        return None

    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Parâmetro data inválido. Use o formato YYYY-MM-DD.") from exc


def _parse_int_opcional(valor: str | None, nome: str):
    if valor in (None, ""):
        return None

    try:
        return int(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Parâmetro {nome} inválido.") from exc


def _parse_limite(valor: str | None) -> int:
    if valor in (None, ""):
        return 50

    try:
        limite = int(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError("Parâmetro limite inválido.") from exc

    if limite < 1:
        return 1

    if limite > 200:
        return 200

    return limite


@briefing_bp.route("/diario", methods=["GET"])
@jwt_required()
def briefing_diario():
    try:
        escopo = request.args.get("escopo", "chamados")
        data_referencia = _parse_data_referencia(request.args.get("data"))
        responsavel_id = _parse_int_opcional(
            request.args.get("responsavel_id"),
            "responsavel_id",
        )
        limite = _parse_limite(request.args.get("limite"))

        resultado = gerar_briefing_diario(
            data_referencia=data_referencia,
            escopo=escopo,
            responsavel_id=responsavel_id,
            limite=limite,
        )

        return jsonify(resultado), 200

    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400

    except Exception:
        return jsonify({"erro": "Erro ao gerar briefing diário."}), 500