"""
Capacity Calculation Service
Validates temporal feasibility of scheduling and calculates capacity metrics.
"""
from typing import List, Dict, Optional
from datetime import datetime, time, timedelta
from flask import current_app

from ..models import Chamado, Usuario, Usina, ConfiguracaoOperacional
from .. import db
from .route_optimization_service import RouteOptimizationService


class CapacityCalculationService:
    """Service for calculating and validating technician capacity"""
    
    @staticmethod
    def validar_viabilidade(tecnico_id: int, data: str, lista_os_ids: List[int]) -> Dict:
        """
        Validate if a set of OS fits within the technician's working hours.
        
        Args:
            tecnico_id: ID of the technician
            data: Date string in format YYYY-MM-DD
            lista_os_ids: List of OS IDs to validate
            
        Returns:
            Dict with viability status and detailed breakdown
        """
        # Get technician info
        tecnico = Usuario.query.get(tecnico_id)
        if not tecnico:
            raise ValueError(f"Técnico {tecnico_id} não encontrado")
        
        # Get configuration
        config = ConfiguracaoOperacional.query.first()
        if not config:
            # Create default config if not exists
            config = ConfiguracaoOperacional(
                margem_seguranca_minutos=30,
                velocidade_media_kmh=50.0
            )
            db.session.add(config)
            db.session.commit()
        
        # Get OS details
        chamados = Chamado.query.filter(Chamado.id_chamado.in_(lista_os_ids)).all()
        
        if not chamados:
            return {
                "viavel": True,
                "status": "viavel",
                "tempo_total_minutos": 0,
                "tempo_disponivel_minutos": 0,
                "tempo_restante_minutos": 0,
                "km_total": 0.0,
                "detalhamento": [],
                "alertas": []
            }
        
        # Calculate available time
        horario_inicio = tecnico.horario_inicio or time(8, 0)
        horario_fim = tecnico.horario_fim or time(18, 0)
        
        inicio_dt = datetime.combine(datetime.today(), horario_inicio)
        fim_dt = datetime.combine(datetime.today(), horario_fim)
        tempo_disponivel_minutos = int((fim_dt - inicio_dt).total_seconds() / 60)
        
        # Get base coordinates
        base_coords = {
            "latitude": float(tecnico.latitude_base) if tecnico.latitude_base else -24.465241,
            "longitude": float(tecnico.longitude_base) if tecnico.longitude_base else -53.952700
        }
        
        # Build OS list with coordinates
        lista_os = []
        for chamado in chamados:
            usina = chamado.usina
            if usina and usina.latitude and usina.longitude:
                lista_os.append({
                    "id": chamado.id_chamado,
                    "cliente": chamado.cliente.nome if chamado.cliente else "Cliente",
                    "latitude": float(usina.latitude),
                    "longitude": float(usina.longitude),
                    "tempo_estimado_minutos": chamado.tempo_estimado_minutos or 120,
                    "prioridade": chamado.prioridade
                })
        
        if not lista_os:
            return {
                "viavel": False,
                "status": "erro",
                "tempo_total_minutos": 0,
                "tempo_disponivel_minutos": tempo_disponivel_minutos,
                "tempo_restante_minutos": tempo_disponivel_minutos,
                "km_total": 0.0,
                "detalhamento": [],
                "alertas": ["⚠️ Nenhuma OS possui coordenadas válidas"]
            }
        
        # Optimize route sequence
        route_service = RouteOptimizationService()
        lista_os_otimizada = route_service.otimizar_sequencia(base_coords, lista_os)
        
        # Calculate complete route
        rota_completa = route_service.calcular_rota_completa(base_coords, lista_os_otimizada)
        
        # Build detailed breakdown
        detalhamento = []
        tempo_total_minutos = 0
        km_total = rota_completa['distancia_total_km']
        
        # Add route segments
        for segmento in rota_completa['segmentos']:
            detalhamento.append({
                "tipo": "deslocamento",
                "de": segmento['de'],
                "para": segmento['para'],
                "tempo": segmento['tempo_minutos'],
                "km": segmento['distancia_km']
            })
            tempo_total_minutos += segmento['tempo_minutos']
        
        # Add execution time for each OS (interleaved with route segments)
        detalhamento_final = []
        seg_index = 0
        for i, os_item in enumerate(lista_os_otimizada):
            # Add travel segment
            if seg_index < len(rota_completa['segmentos']):
                detalhamento_final.append(detalhamento[seg_index])
                seg_index += 1
            
            # Add execution time
            detalhamento_final.append({
                "tipo": "execucao",
                "os_id": os_item['id'],
                "cliente": os_item['cliente'],
                "tempo": os_item['tempo_estimado_minutos']
            })
            tempo_total_minutos += os_item['tempo_estimado_minutos']
        
        # Add return segment
        if seg_index < len(rota_completa['segmentos']):
            detalhamento_final.append(detalhamento[seg_index])
        
        # Add safety margin
        tempo_total_minutos += config.margem_seguranca_minutos
        detalhamento_final.append({
            "tipo": "margem_seguranca",
            "tempo": config.margem_seguranca_minutos
        })
        
        # Calculate remaining time
        tempo_restante_minutos = tempo_disponivel_minutos - tempo_total_minutos
        
        # Determine status
        percentual_uso = (tempo_total_minutos / tempo_disponivel_minutos) * 100 if tempo_disponivel_minutos > 0 else 100
        
        if percentual_uso <= 85:
            status = "viavel"
            viavel = True
            alertas = []
        elif percentual_uso <= 100:
            status = "atencao"
            viavel = True
            alertas = [f"⚠️ Planejamento usa {percentual_uso:.0f}% da capacidade"]
        else:
            status = "excede"
            viavel = False
            tempo_excesso = tempo_total_minutos - tempo_disponivel_minutos
            alertas = [
                f"❌ Planejamento excede expediente em {tempo_excesso} minutos",
                "💡 Considere remover OS de menor prioridade ou reagendar"
            ]
        
        return {
            "viavel": viavel,
            "status": status,
            "tempo_total_minutos": round(tempo_total_minutos, 1),
            "tempo_disponivel_minutos": tempo_disponivel_minutos,
            "tempo_restante_minutos": round(tempo_restante_minutos, 1),
            "km_total": km_total,
            "detalhamento": detalhamento_final,
            "alertas": alertas
        }
    
    @staticmethod
    def calcular_impacto_adicionar_os(tecnico_id: int, data: str, nova_os_id: int) -> Dict:
        """
        Calculate the impact of adding a new OS to a technician's day.
        
        Args:
            tecnico_id: ID of the technician
            data: Date string in format YYYY-MM-DD
            nova_os_id: ID of the OS to add
            
        Returns:
            Dict with impact analysis
        """
        # Get existing OS for this technician on this date
        data_obj = datetime.strptime(data, '%Y-%m-%d').date()
        
        chamados_existentes = Chamado.query.filter(
            Chamado.id_usuario_responsavel == tecnico_id,
            Chamado.status == 'Agendando Visita',
            db.func.date(Chamado.data_agendamento) == data_obj
        ).all()
        
        lista_os_ids_existentes = [c.id_chamado for c in chamados_existentes]
        
        # Validate current state
        if lista_os_ids_existentes:
            estado_atual = CapacityCalculationService.validar_viabilidade(
                tecnico_id, data, lista_os_ids_existentes
            )
        else:
            estado_atual = {
                "tempo_total_minutos": 0,
                "tempo_restante_minutos": 600,  # Default 10h
                "km_total": 0.0,
                "status": "viavel"
            }
        
        # Validate with new OS added
        lista_os_ids_nova = lista_os_ids_existentes + [nova_os_id]
        estado_novo = CapacityCalculationService.validar_viabilidade(
            tecnico_id, data, lista_os_ids_nova
        )
        
        # Calculate deltas
        delta_tempo = estado_novo['tempo_total_minutos'] - estado_atual['tempo_total_minutos']
        delta_km = estado_novo['km_total'] - estado_atual['km_total']
        
        return {
            "estado_atual": estado_atual,
            "estado_novo": estado_novo,
            "impacto": {
                "delta_tempo_minutos": round(delta_tempo, 1),
                "delta_km": round(delta_km, 2),
                "status_muda_de": estado_atual['status'],
                "status_muda_para": estado_novo['status']
            },
            "recomendacao": "aceitar" if estado_novo['viavel'] else "recusar"
        }
