from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Any

app = FastAPI(
    title="SmartCheck AI Engine",
    description="Motor RAG de priorización para RedCheck",
    version="1.0.0"
)

class TaskPayload(BaseModel):
    userId: str
    tasks: List[Any] 

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "smartcheck-ai-engine"}

@app.post("/api/v1/prioritize")
async def prioritize_tasks(payload: TaskPayload):
    return {
        "nivelRiesgo": "BAJO",
        "mensajeApoyo": "Mock inicial. El contenedor está recibiendo la carga.",
        "planDeHoy": payload.tasks
    }
