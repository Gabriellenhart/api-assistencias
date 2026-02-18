"""
Rescheduling Service
Provides intelligent rescheduling suggestions when OS doesn't fit in current schedule.
"""
from typing import List, Dict
from datetime import datetime, timedelta
from flask import current_app

from ..models import Chamado, Usuario
from .. import db
from .capacity_calculation_service import CapacityCalculationService


class ReschedulingService:
    """Service for suggesting optimal rescheduling options"""
    
    @staticmethod
    def sugerir_reagendamento(os_id: int, dias_futuros: int = 7) -> Dict:
        """
        Suggest best rescheduling options for an OS.
        
        Args:
            os_id: ID of the OS to reschedule
            dias_futuros: Number of days to look ahead
            
        Returns:
            Dict with OS info and list of suggestions
        """
        # Get OS details
        chamado = Chamado.query.get(os_id)
        if not chamado:
            raise ValueError(f"Chamado {os_id} não encontrado")
        
        # Get all technicians
        tecnicos = Usuario.query.filter(
            Usuario.nivel.in_(['tecnico', 'supervisor'])
        ).all()
        
        if not tecnicos:
            return {
                "os": {
                    "id": os_id,
                    "cliente": chamado.cliente.nome if chamado.cliente else "Cliente",
                    "prioridade": chamado.prioridade,
                    "tempo_estimado": chamado.tempo_estimado_minutos or 120
                },
                "sugestoes": []
            }
        
        # Generate suggestions for next N days
        sugestoes = []
        hoje = datetime.now().date()
        
        capacity_service = CapacityCalculationService()
        
        for dia_offset in range(1, dias_futuros + 1):
            data_candidata = hoje + timedelta(days=dia_offset)
            
            # Skip weekends (Saturday=5, Sunday=6)
            if data_candidata.weekday() >= 5:
                continue
            
            data_str = data_candidata.strftime('%Y-%m-%d')
            
            for tecnico in tecnicos:
                try:
                    # Calculate impact of adding this OS
                    impacto = capacity_service.calcular_impacto_adicionar_os(
                        tecnico.id_usuario,
                        data_str,
                        os_id
                    )
                    
                    if impacto['recomendacao'] == 'aceitar':
                        # Determine reason/motivation
                        motivo = ReschedulingService._determinar_motivo(impacto, tecnico, chamado)
                        
                        sugestoes.append({
                            "tecnico_id": tecnico.id_usuario,
                            "tecnico_nome": tecnico.nome_usuario,
                            "data": data_str,
                            "impacto_km": impacto['impacto']['delta_km'],
                            "tempo_restante_apos": impacto['estado_novo']['tempo_restante_minutos'],
                            "status": impacto['estado_novo']['status'],
                            "motivo": motivo,
                            "score": ReschedulingService._calcular_score(impacto, dia_offset, chamado)
                        })
                
                except Exception as e:
                    current_app.logger.error(f"Error calculating impact for tech {tecnico.id_usuario}: {e}")
                    continue
        
        # Sort suggestions by score (higher is better)
        sugestoes_ordenadas = sorted(sugestoes, key=lambda x: x['score'], reverse=True)
        
        # Remove score from output (internal use only)
        for sug in sugestoes_ordenadas:
            sug.pop('score', None)
        
        return {
            "os": {
                "id": os_id,
                "cliente": chamado.cliente.nome if chamado.cliente else "Cliente",
                "prioridade": chamado.prioridade,
                "tempo_estimado": chamado.tempo_estimado_minutos or 120
            },
            "sugestoes": sugestoes_ordenadas[:10]  # Return top 10
        }
    
    @staticmethod
    def _determinar_motivo(impacto: Dict, tecnico: Usuario, chamado: Chamado) -> str:
        """Determine the reason/motivation for this suggestion"""
        delta_km = impacto['impacto']['delta_km']
        tempo_restante = impacto['estado_novo']['tempo_restante_minutos']
        
        if delta_km < 10:
            return "Mesmo eixo de rota, menor km incremental"
        elif tempo_restante > 180:
            return "Menor carga no dia"
        elif tecnico.id_usuario == chamado.id_usuario_responsavel:
            return "Mesmo técnico já atribuído"
        else:
            return "Disponibilidade compatível"
    
    @staticmethod
    def _calcular_score(impacto: Dict, dia_offset: int, chamado: Chamado) -> float:
        """
        Calculate a score for ranking suggestions.
        Higher score = better suggestion.
        """
        score = 100.0
        
        # Prefer sooner dates
        score -= dia_offset * 5
        
        # Prefer lower km impact
        delta_km = impacto['impacto']['delta_km']
        score -= delta_km * 0.5
        
        # Prefer more remaining time
        tempo_restante = impacto['estado_novo']['tempo_restante_minutos']
        score += tempo_restante * 0.1
        
        # Boost if status is "viavel" vs "atencao"
        if impacto['estado_novo']['status'] == 'viavel':
            score += 20
        
        # Priority boost (Alta priority should be scheduled sooner)
        if chamado.prioridade == 'Alta':
            score += 30 - (dia_offset * 10)
        
        return score
