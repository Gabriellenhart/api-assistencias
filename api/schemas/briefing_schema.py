# api/schemas/briefing_schema.py

from pydantic import BaseModel
from typing import List, Dict, Any

class TaskDetail(BaseModel):
    ordem: int
    tipo: str
    id: int
    codigo: str
    status: str
    
    # Campos derivados baseados nos dados do banco
    score: int
    
    # Campos derivados que serão calculados no backend
    score_calculated: int

class SummaryModel(BaseModel):
    total_tasks: int
    summary: dict  # Contém os totais agregados
    tasks: list[SummaryModel]

# Nota: O modelo final será uma estrutura JSON aninhada