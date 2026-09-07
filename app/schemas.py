from pydantic import BaseModel, Field
from typing import List, Optional

class TaskPlan(BaseModel):
    id: int = Field(
        description="Task ID"
    )
    ordenDefinido: int = Field(
        description="Assigned priority order"
    )
    razonPrioridad: str = Field(
        description="Detailed explanation of why it was assigned this specific order"
    )

class PrioritizationResponse(BaseModel):
    nivelRiesgo: str = Field(
        description="Overall risk level: HIGH, MEDIUM, or LOW"
    )
    mensajeApoyo: str = Field(
        description="Motivational and analytical support message for the user"
    )
    planDeHoy: List[TaskPlan] = Field(
        description="Ordered list of tasks for today providing full coverage"
    )

class TaskOutcomePayload(BaseModel):
    """Mirrors the `simplifiedTasks` shape RedCheck's SmartCheckAIService builds
    for `/prioritize` (id, titulo, fechaLimite, asignatura — Spanish keys,
    subject name already resolved server-side), plus the completion/ordering
    fields needed to record an outcome. This is the AI-engine-facing task
    contract; RedCheck's frontend-facing TaskResponse (English keys) is a
    different, unrelated shape used for CRUD/display, not for talking to
    this service."""

    userId: str = Field(description="ID of the task's owner")
    id: int = Field(description="Task ID, matching the id used in /prioritize")
    titulo: str = Field(description="Task title")
    asignatura: str = Field(
        default="", description="Subject/project name, already resolved (same as in /prioritize)"
    )
    fechaLimite: Optional[str] = Field(default=None, description="Original due date (ISO 8601), if any")
    completada: bool = Field(description="Whether the task was completed")
    fechaCompletado: Optional[str] = Field(
        default=None, description="Actual completion date (ISO 8601), if the task was completed"
    )
    ordenSugeridoIA: Optional[int] = Field(
        default=None, description="Order SmartCheck AI assigned to this task on its planning day"
    )
    ordenReal: Optional[int] = Field(
        default=None, description="Actual order in which the user tackled the task that day"
    )
