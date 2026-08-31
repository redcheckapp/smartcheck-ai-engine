from pydantic import BaseModel, Field
from typing import List

class TaskPlan(BaseModel):
    id: int = Field(description="ID de la tarea")
    ordenDefinido: int = Field(description="Orden de prioridad asignado")
    razonPrioridad: str = Field(description="Explicación detallada de por qué tiene este orden")

class PrioritizationResponse(BaseModel):
    nivelRiesgo: str = Field(description="Nivel de riesgo general: HIGH, MEDIUM o LOW")
    mensajeApoyo: str = Field(description="Mensaje motivacional y analítico para el usuario")
    planDeHoy: List[TaskPlan] = Field(description="Lista ordenada de tareas para hoy con cobertura total")