from pydantic import BaseModel, Field
from typing import List

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