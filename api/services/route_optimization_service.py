"""
Route Optimization Service
Handles route calculation, optimization, and distance/time estimation for field service scheduling.
"""
import requests
import math
from typing import List, Dict, Tuple, Optional
from flask import current_app

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"


class RouteOptimizationService:
    """Service for calculating and optimizing routes between service locations"""
    
    @staticmethod
    def calcular_rota(origem: Dict[str, float], destino: Dict[str, float]) -> Dict:
        """
        Calculate route between two points using OSRM.
        
        Args:
            origem: Dict with 'latitude' and 'longitude'
            destino: Dict with 'latitude' and 'longitude'
            
        Returns:
            Dict with:
                - distancia_km: float
                - tempo_minutos: float
                - geometria: GeoJSON geometry for map rendering
        """
        try:
            origem_coords = f"{origem['longitude']},{origem['latitude']}"
            destino_coords = f"{destino['longitude']},{destino['latitude']}"
            
            url = f"{OSRM_URL}/{origem_coords};{destino_coords}?overview=full&geometries=geojson"
            
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if not data.get("routes"):
                # Fallback to haversine calculation
                return RouteOptimizationService._calcular_rota_haversine(origem, destino)
            
            route = data["routes"][0]
            distancia_m = route["distance"]
            duracao_s = route["duration"]
            
            return {
                "distancia_km": round(distancia_m / 1000.0, 2),
                "tempo_minutos": round(duracao_s / 60.0, 1),
                "geometria": route.get("geometry")
            }
            
        except Exception as e:
            current_app.logger.warning(f"OSRM route calculation failed: {e}. Using haversine fallback.")
            return RouteOptimizationService._calcular_rota_haversine(origem, destino)
    
    @staticmethod
    def _calcular_rota_haversine(origem: Dict[str, float], destino: Dict[str, float]) -> Dict:
        """
        Fallback route calculation using Haversine formula.
        Returns straight-line distance × 1.3 to approximate road distance.
        """
        lat1 = math.radians(origem['latitude'])
        lon1 = math.radians(origem['longitude'])
        lat2 = math.radians(destino['latitude'])
        lon2 = math.radians(destino['longitude'])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth radius in km
        r = 6371
        
        distancia_linha_reta = r * c
        distancia_estrada = distancia_linha_reta * 1.3  # Approximate road factor
        
        # Estimate time based on average speed (from config or default 50 km/h)
        velocidade_media = current_app.config.get('VELOCIDADE_MEDIA_KMH', 50.0)
        tempo_minutos = (distancia_estrada / velocidade_media) * 60
        
        return {
            "distancia_km": round(distancia_estrada, 2),
            "tempo_minutos": round(tempo_minutos, 1),
            "geometria": None  # No geometry for haversine
        }
    
    @staticmethod
    def calcular_rota_completa(base: Dict[str, float], lista_os: List[Dict]) -> Dict:
        """
        Calculate complete route: base → OS1 → OS2 → ... → base
        
        Args:
            base: Dict with 'latitude' and 'longitude' of base location
            lista_os: List of OS dicts, each with 'latitude' and 'longitude'
            
        Returns:
            Dict with:
                - pontos: List of waypoints
                - distancia_total_km: float
                - tempo_total_minutos: float
                - geometria: Combined GeoJSON geometry
                - segmentos: List of individual route segments
        """
        if not lista_os:
            return {
                "pontos": [base],
                "distancia_total_km": 0.0,
                "tempo_total_minutos": 0.0,
                "geometria": None,
                "segmentos": []
            }
        
        pontos = [{"tipo": "base", "nome": "Base", **base}]
        segmentos = []
        distancia_total = 0.0
        tempo_total = 0.0
        
        # Base → First OS
        origem = base
        for i, os_item in enumerate(lista_os):
            destino = {"latitude": os_item['latitude'], "longitude": os_item['longitude']}
            
            rota = RouteOptimizationService.calcular_rota(origem, destino)
            
            segmentos.append({
                "de": origem.get('nome', 'Base' if i == 0 else lista_os[i-1].get('cliente', 'OS')),
                "para": os_item.get('cliente', f"OS #{os_item.get('id', '?')}"),
                "distancia_km": rota['distancia_km'],
                "tempo_minutos": rota['tempo_minutos']
            })
            
            pontos.append({
                "tipo": "os",
                "id": os_item.get('id'),
                "nome": os_item.get('cliente', 'Cliente'),
                "latitude": os_item['latitude'],
                "longitude": os_item['longitude']
            })
            
            distancia_total += rota['distancia_km']
            tempo_total += rota['tempo_minutos']
            
            origem = destino
        
        # Last OS → Base
        rota_retorno = RouteOptimizationService.calcular_rota(origem, base)
        segmentos.append({
            "de": lista_os[-1].get('cliente', 'Última OS'),
            "para": "Base",
            "distancia_km": rota_retorno['distancia_km'],
            "tempo_minutos": rota_retorno['tempo_minutos']
        })
        
        pontos.append({"tipo": "base", "nome": "Base (Retorno)", **base})
        
        distancia_total += rota_retorno['distancia_km']
        tempo_total += rota_retorno['tempo_minutos']
        
        return {
            "pontos": pontos,
            "distancia_total_km": round(distancia_total, 2),
            "tempo_total_minutos": round(tempo_total, 1),
            "geometria": None,  # TODO: Combine geometries if needed
            "segmentos": segmentos
        }
    
    @staticmethod
    def otimizar_sequencia(base: Dict[str, float], lista_os: List[Dict]) -> List[Dict]:
        """
        Optimize the sequence of OS visits using nearest neighbor heuristic.
        
        Args:
            base: Dict with 'latitude' and 'longitude'
            lista_os: List of OS dicts to optimize
            
        Returns:
            Optimized list of OS in best visiting order
        """
        if len(lista_os) <= 1:
            return lista_os
        
        # Simple nearest neighbor algorithm
        nao_visitados = lista_os.copy()
        sequencia_otimizada = []
        posicao_atual = base
        
        while nao_visitados:
            # Find nearest OS from current position
            menor_distancia = float('inf')
            proximo_os = None
            proximo_index = -1
            
            for i, os_item in enumerate(nao_visitados):
                destino = {"latitude": os_item['latitude'], "longitude": os_item['longitude']}
                rota = RouteOptimizationService.calcular_rota(posicao_atual, destino)
                
                if rota['distancia_km'] < menor_distancia:
                    menor_distancia = rota['distancia_km']
                    proximo_os = os_item
                    proximo_index = i
            
            if proximo_os:
                sequencia_otimizada.append(proximo_os)
                posicao_atual = {"latitude": proximo_os['latitude'], "longitude": proximo_os['longitude']}
                nao_visitados.pop(proximo_index)
        
        return sequencia_otimizada
