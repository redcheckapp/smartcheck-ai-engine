from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from app.services.vector_store import query_context
from app.services.llm_engine import generate_prioritized_plan

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
    
    docs = query_context(payload.userId, f"Rendimiento previo relacionado con: {nombres_tareas}")
    rag_context = "\n".join(docs) if docs else ""
    
    plan_json = generate_prioritized_plan(
        tasks=payload.tasks,
        user_analytics=payload.userAnalytics,
        rag_context=rag_context,
        user_profile=payload.userProfile,
        lang=payload.lang # <-- Parámetro inyectado aquí
    )
    
    return plan_json