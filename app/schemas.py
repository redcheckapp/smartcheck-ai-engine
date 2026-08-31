from pydantic import BaseModel, Field
from typing import List
from enum import Enum

class NivelRiesgo(str, Enum):
    ALTO = "ALTO"
    MEDIO = "MEDIO"
    BAJO = "BAJO"

class PlanItem(BaseModel):
    id: str = Field(description="ID original de la tarea")
    ordenDefinido: int = Field(description="Posición final en la lista priorizada")
    razonPrioridad: str = Field(description="Justificación analítica breve de por qué se asignó este orden")

class PrioritizationResponse(BaseModel):
    nivelRiesgo: NivelRiesgo
    mensajeApoyo: str = Field(description="Mensaje motivacional breve basado en el nivel de riesgo")
    planDeHoy: List[PlanItem] = Field(description="Array ordenado con la estrategia de ejecución")