from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
from services.vector_store import query_context
from services.llm_engine import generate_prioritized_plan

app = FastAPI(
    title="SmartCheck AI Engine",
    version="1.0.0"
)

# Actualizamos el contrato para recibir analíticas del usuario desde Spring Boot
class TaskPayload(BaseModel):
    userId: str
    userAnalytics: Dict[str, int] # ej: {"Ciberseguridad": 17, "Backend": 50}
    tasks: List[Any]

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/v1/prioritize")
async def prioritize_tasks(payload: TaskPayload):
    # 1. Extraemos el contexto de todas las tareas como una sola consulta RAG
    # Para afinarlo, podrías iterar, pero una consulta general con los títulos suele bastar.
    nombres_tareas = ", ".join([t.get("titulo", "") for t in payload.tasks])
    
    docs = query_context(payload.userId, f"Rendimiento previo relacionado con: {nombres_tareas}")
    rag_context = "\n".join(docs) if docs else ""
    
    # 2. Inyectamos tareas, analíticas y memoria en el motor LLM
    plan_json = generate_prioritized_plan(
        tasks=payload.tasks,
        user_analytics=payload.userAnalytics,
        rag_context=rag_context
    )
    
    # 3. Retornamos la respuesta estructurada a Spring Boot
    return plan_json