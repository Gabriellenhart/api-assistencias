# services/deslocamento_service.py
import requests
import math

from flask import current_app

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"

def calcular_rota_osrm(dest_lat, dest_lon):
    """
    Calcula rota usando OSRM público. Retorna:
    - distancia_ida_km
    - duracao_min
    - geometry (geojson da rota) para desenhar no mapa.
    """
    # Busca coordenadas do config
    empresa_lat = current_app.config.get("EMPRESA_LATITUDE")
    empresa_lon = current_app.config.get("EMPRESA_LONGITUDE")

    if not empresa_lat or not empresa_lon:
        raise RuntimeError("Coordenadas da empresa não configuradas no config.py")

    origem = f"{empresa_lon},{empresa_lat}"
    destino = f"{dest_lon},{dest_lat}"
    url = f"{OSRM_URL}/{origem};{destino}?overview=full&geometries=geojson"

    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("routes"):
        raise RuntimeError("Nenhuma rota encontrada pelo OSRM")

    route = data["routes"][0]
    distancia_m = route["distance"]
    duracao_s = route["duration"]

    distancia_km = distancia_m / 1000.0
    duracao_min = duracao_s / 60.0

    return distancia_km, duracao_min, route.get("geometry")


def obter_valor_hora_tecnica(distancia_km_ida, perfil_cobranca):
    """
    Retorna o valor da HORA TÉCNICA (por técnico) com base na distância e na tabela:

    Tabela 1:
      até 30km       ->  60/h
      30–100km       ->  80/h
      acima 100km    -> 100/h

    Tabela 2:
      até 30km       ->  90/h
      30–100km       -> 120/h
      acima 100km    -> 150/h
    """
    dist = float(distancia_km_ida or 0)

    if perfil_cobranca == "tabela2":
        # 90 / 120 / 150
        if dist <= 30:
            return 90.0
        elif dist <= 100:
            return 120.0
        else:
            return 150.0
    else:
        # tabela1 (padrão): 60 / 80 / 100
        if dist <= 30:
            return 60.0
        elif dist <= 100:
            return 80.0
        else:
            return 100.0


def calcular_atendimento(distancia_km_ida, horas_previstas, perfil_cobranca, qtd_tecnicos=1):
    """
    Aplica as regras:
    - deslocamento: R$ 2,00/km (ida e volta)
    - hora técnica: mínimo 1h, multiplicado por nº de técnicos
    """
    qtd_tecnicos = int(qtd_tecnicos or 1)
    if qtd_tecnicos < 1:
        qtd_tecnicos = 1

    dist_ida = float(distancia_km_ida or 0.0)
    dist_total = dist_ida * 2.0  # ida + volta

    valor_deslocamento = dist_total * 2.0  # R$ 2,00/km

    horas = float(horas_previstas or 0.0)
    if horas < 1.0:
        horas = 1.0  # mínimo 1h

    valor_hora_unit = obter_valor_hora_tecnica(dist_ida, perfil_cobranca)
    valor_horas_total = valor_hora_unit * horas * qtd_tecnicos

    valor_total = valor_deslocamento + valor_horas_total

    return {
        "distancia_km_ida": dist_ida,
        "distancia_km_total": dist_total,
        "valor_deslocamento": math.ceil(valor_deslocamento),
        "valor_hora_unitaria": round(valor_hora_unit, 2),
        "horas_cobradas": horas,
        "qtd_tecnicos": qtd_tecnicos,
        "valor_horas_total": round(valor_horas_total, 2),
        "valor_total_atendimento": round(valor_total, 2),
    }
