# /api/services/geolocation_service.py  (VERSÃO FINAL COM CORREÇÕES)

import logging
from decimal import Decimal, InvalidOperation, ROUND_UP, ROUND_HALF_UP
from typing import Dict, Any, List, Tuple

import requests
from flask import current_app


def _as_decimal(value: Any, default: str = "0") -> Decimal:
    """
    Converte um valor para Decimal sem vazamento de binário.
    Usa string como fonte sempre que possível.
    """
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _format_money_2dec_up_to_int(amount: Decimal) -> str:
    """
    Arredonda para CIMA (ceil) ao inteiro mais próximo e formata com 2 casas.
    Ex.: 64.41 -> 65.00 ; 65.00 -> 65.00 ; 65.01 -> 66.00
    """
    arredondado_inteiro = amount.quantize(Decimal("1"), rounding=ROUND_UP)
    # Garante duas casas apenas para formatação/JSON:
    return f"{arredondado_inteiro.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def _swap_lonlat_to_latlon(coords: List[List[float]]) -> List[List[float]]:
    """
    OSRM retorna [lon, lat]; o front costuma esperar [lat, lon].
    """
    return [[c[1], c[0]] for c in coords if isinstance(c, (list, tuple)) and len(c) >= 2]


def calcular_distancia_e_custo(lat_destino: Any, lon_destino: Any) -> Dict[str, Any]:
    """
    Calcula a rota (OSRM), distância, tempo estimado e custo de deslocamento,
    fazendo o arredondamento do valor para cima ao inteiro mais próximo (formato "xx.00").

    Retorno (sempre serializável em JSON):
    {
        "distancia_km": "16.10",          # string com 2 casas
        "tempo_estimado": "0h 19min",     # string
        "valor_deslocamento": "65.00",    # string com 2 casas (inteiro cheio)
        "geometry": [[lat, lon], ...]     # lista de pares
    }
    """
    try:
        # --- Origens da empresa (config) ---
        base_lat = current_app.config.get("EMPRESA_LATITUDE")
        base_lon = current_app.config.get("EMPRESA_LONGITUDE")

        # Validações mínimas de config
        if base_lat is None or base_lon is None:
            raise RuntimeError("EMPRESA_LATITUDE/EMPRESA_LONGITUDE ausentes no config.")

        custo_km = _as_decimal(current_app.config.get("CUSTO_POR_KM"), default="0")

        # Normaliza destino para string (evita float binário no URL)
        lat_destino_str = str(lat_destino)
        lon_destino_str = str(lon_destino)

        # --- Chamada OSRM ---
        url = (
            "http://router.project-osrm.org/route/v1/driving/"
            f"{base_lon},{base_lat};{lon_destino_str},{lat_destino_str}"
            "?overview=full&geometries=geojson"
        )
        logging.info(f"Calculando rota OSRM: {url}")

        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            msg = data.get("message", "Rota não encontrada")
            logging.warning(f"OSRM não encontrou rota: {msg}")
            raise RuntimeError(msg)

        route = data["routes"][0]

        # Distância (m) e duração (s) vindas do OSRM
        distancia_m = _as_decimal(route.get("distance", 0))
        duracao_s = _as_decimal(route.get("duration", 0))

        # Converte para km 100% em Decimal (sem dividir por float)
        distancia_km = (distancia_m / Decimal("1000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Tempo estimado (formata inteiro de horas e minutos)
        total_segundos = int(duracao_s) if duracao_s.is_finite() else 0
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        tempo_estimado = f"{horas}h {minutos}min"

        # Cálculo do custo: ida e volta => * 2
        # Tudo em Decimal, sem floats.
        valor_bruto = (distancia_km * custo_km * Decimal("2"))
        valor_deslocamento = _format_money_2dec_up_to_int(valor_bruto)

        # Geometria (lon,lat) -> (lat,lon)
        coords = route.get("geometry", {}).get("coordinates", []) or []
        geometry = _swap_lonlat_to_latlon(coords)

        return {
            "distancia_km": f"{distancia_km:.2f}",
            "tempo_estimado": tempo_estimado,
            "valor_deslocamento": valor_deslocamento,  # "65.00" etc.
            "geometry": geometry,
        }

    except Exception as e:
        logging.error(f"Erro ao calcular deslocamento: {e}")
        # Retorno seguro/serializável
        return {
            "distancia_km": "0.00",
            "tempo_estimado": "N/A",
            "valor_deslocamento": "0.00",
            "geometry": [],
        }
