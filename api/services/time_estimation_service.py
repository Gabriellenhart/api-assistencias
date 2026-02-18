"""
Time Estimation Service
Estimates execution time based on service category and historical data.
"""
from typing import Optional
from flask import current_app

from ..models import ConfiguracaoOperacional, Chamado
from .. import db


class TimeEstimationService:
    """Service for estimating and updating execution times"""
    
    @staticmethod
    def estimar_tempo_execucao(categoria: str, tipo_servico: Optional[str] = None) -> int:
        """
        Estimate execution time in minutes based on category.
        
        Args:
            categoria: Service category
            tipo_servico: Optional service type for more specific estimation
            
        Returns:
            Estimated time in minutes
        """
        # Get configuration
        config = ConfiguracaoOperacional.query.first()
        
        if config and config.tempo_medio_por_categoria:
            tempo_medio = config.tempo_medio_por_categoria.get(categoria)
            if tempo_medio:
                return int(tempo_medio)
        
        # Default estimates by category
        defaults = {
            "Manutenção Preventiva": 90,
            "Instalação": 180,
            "Reparo": 120,
            "Vistoria": 60,
            "Garantia": 90,
            "Emergência": 150
        }
        
        return defaults.get(categoria, 120)  # Default 2 hours
    
    @staticmethod
    def atualizar_estimativa_historico(os_id: int, tempo_real_minutos: int):
        """
        Update historical average after OS completion.
        This would be called when an OS is marked as completed.
        
        Args:
            os_id: ID of the completed OS
            tempo_real_minutos: Actual time spent in minutes
        """
        # Get the OS to find its category
        from ..models import OrdenServico
        
        os = OrdenServico.query.get(os_id)
        if not os or not os.chamado:
            return
        
        categoria = os.chamado.categoria
        
        # Get current configuration
        config = ConfiguracaoOperacional.query.first()
        if not config:
            return
        
        # Update running average
        if not config.tempo_medio_por_categoria:
            config.tempo_medio_por_categoria = {}
        
        tempo_atual = config.tempo_medio_por_categoria.get(categoria, 120)
        
        # Simple moving average (weighted 70% old, 30% new)
        novo_tempo = int(tempo_atual * 0.7 + tempo_real_minutos * 0.3)
        
        config.tempo_medio_por_categoria[categoria] = novo_tempo
        
        db.session.commit()
        
        current_app.logger.info(
            f"Updated time estimate for {categoria}: {tempo_atual}min → {novo_tempo}min"
        )
