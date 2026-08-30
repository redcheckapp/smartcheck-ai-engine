from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from services.vector_store import upsert_task, query_context
from typing import List, Any

app = FastAPI()

class TaskHistoryPayload(BaseModel):
    taskId: str
    userId: str
    taskDescription: str
    timeSpentHours: float
    status: str

class QueryPayload(BaseModel):
    userId: str
    query: str

@app.post("/api/v1/history")
async def save_history(payload: TaskHistoryPayload, bg_tasks: BackgroundTasks):
    context_text = f"La tarea '{payload.taskDescription}' tomó {payload.timeSpentHours} horas y su estado es {payload.status}."
    
    # Lo ejecutamos en segundo plano para no bloquear la respuesta de la API
    bg_tasks.add_task(
        upsert_task, 
        payload.taskId, 
        payload.userId, 
        context_text, 
        {"timeSpent": payload.timeSpentHours, "status": payload.status}
    )
    return {"status": "procesando embedding en background"}

@app.post("/api/v1/query")
async def search_memory(payload: QueryPayload):
    docs = query_context(payload.userId, payload.query)
    return {"contexto_recuperado": docs}