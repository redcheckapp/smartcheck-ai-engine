from pydantic import BaseModel, Field
from typing import List, Optional

class TaskPlan(BaseModel):
    id: int = Field(description="ID de la tarea")
    ordenDefinido: int = Field(description="Orden de prioridad asignado")
    razonPrioridad: str = Field(description="Explicación detallada de por qué tiene este orden")

class PrioritizationResponse(BaseModel):
    nivelRiesgo: str = Field(description="Nivel de riesgo general: HIGH, MEDIUM o LOW")
    mensajeApoyo: str = Field(description="Mensaje motivacional y analítico para el usuario")
    planDeHoy: List[TaskPlan] = Field(description="Lista ordenada de tareas para hoy con cobertura total")

class TaskOutcomePayload(BaseModel):
    """Mirrors the `simplifiedTasks` shape RedCheck's SmartCheckAIService builds
    for `/prioritize` (id, titulo, fechaLimite, asignatura — Spanish keys,
    subject name already resolved server-side), plus the completion/ordering
    fields needed to record an outcome. This is the AI-engine-facing task
    contract; RedCheck's frontend-facing TaskResponse (English keys) is a
    different, unrelated shape used for CRUD/display, not for talking to
    this service."""

    userId: str = Field(description="ID del usuario propietario de la tarea")
    id: int = Field(description="ID de la tarea, igual que en el payload de /prioritize")
    titulo: str = Field(description="Título de la tarea")
    asignatura: str = Field(
        default="", description="Nombre de la asignatura/proyecto, ya resuelto (igual que en /prioritize)"
    )
    fechaLimite: Optional[str] = Field(default=None, description="Fecha límite original (ISO 8601), si la tenía")
    completada: bool = Field(description="Si la tarea se completó")
    fechaCompletado: Optional[str] = Field(
        default=None, description="Fecha real de finalización (ISO 8601), si se completó"
    )
    ordenSugeridoIA: Optional[int] = Field(
        default=None, description="Orden que SmartCheck AI asignó a esta tarea en su día de planificación"
    )
    ordenReal: Optional[int] = Field(
        default=None, description="Orden real en que el usuario abordó la tarea ese día"
    )