from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from app.schemas import TaskOutcomePayload
from app.services.vector_store import build_rag_context
from app.services.llm_engine import generate_prioritized_plan, PrioritizationGenerationError
from app.services.outcome_service import register_task_outcome
from app.services.feature_engineering import enrich_tasks

app = FastAPI(
    title="SmartCheck AI Engine",
    version="1.0.0"
)

class TaskPayload(BaseModel):
    userId: str
    userProfile: str = Field(
        default="Usuario estándar", 
        description="Descripción de las preferencias, metodología y stack del usuario"
    )
    lang: str = Field(
        default="es",
        description="Idioma de la respuesta (es o en)"
    )
    userAnalytics: Dict[str, int]
    tasks: List[Any]

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/v1/prioritize")
async def prioritize_tasks(payload: TaskPayload):
    nombres_tareas = ", ".join([t.get("titulo", "") for t in payload.tasks])
    asignaturas = sorted({t.get("asignatura") for t in payload.tasks if t.get("asignatura")})

    rag_context = build_rag_context(
        payload.userId, f"Rendimiento previo relacionado con: {nombres_tareas}", asignaturas
    )

    enriched_tasks = enrich_tasks(payload.tasks, datetime.now())

    try:
        plan_json = generate_prioritized_plan(
            tasks=enriched_tasks,
            user_analytics=payload.userAnalytics,
            rag_context=rag_context,
            lang=payload.lang
        )
    except PrioritizationGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return plan_json

@app.post("/api/v1/tasks/outcome")
async def register_outcome(payload: TaskOutcomePayload):
    register_task_outcome(payload)
    return {"status": "ok"}