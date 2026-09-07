import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from app.schemas import TaskOutcomePayload
from app.services.vector_store import build_rag_context
from app.services.llm_engine import generate_prioritized_plan, PrioritizationGenerationError
from app.services.outcome_service import register_task_outcome
from app.services.feature_engineering import enrich_tasks

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SmartCheck AI Engine",
    description="RAG-based AI prioritization microservice for RedCheck.",
    version="1.0.0"
)

class TaskPayload(BaseModel):
    userId: str
    userProfile: str = Field(
        default="Standard user",
        description="Description of the user's preferences, methodology, and technical stack"
    )
    lang: str = Field(
        default="en",
        description="Language for the AI response support messages (e.g., 'es' or 'en')"
    )
    userAnalytics: Dict[str, int]
    tasks: List[Dict[str, Any]]

@app.get("/health")
async def health_check():
    """Service heartbeat endpoint for Docker/NGINX routing."""
    return {"status": "ok"}

@app.post("/api/v1/prioritize")
async def prioritize_tasks(payload: TaskPayload):
    """
    Orchestrates task prioritization by combining real-time data with ChromaDB RAG context.
    """
    try:
        # SmartCheckAIService (Java) sends `titulo`; `title` is kept as a fallback
        # in case that ever changes upstream — see CLAUDE.md for the full story.
        nombres_tareas = ", ".join([t.get("titulo", t.get("title", "")) for t in payload.tasks])
        asignaturas = sorted({t.get("asignatura") for t in payload.tasks if t.get("asignatura")})

        rag_context = build_rag_context(
            payload.userId, f"Rendimiento previo relacionado con: {nombres_tareas}", asignaturas
        )

        enriched_tasks = enrich_tasks(payload.tasks, datetime.now())

        plan_json = generate_prioritized_plan(
            tasks=enriched_tasks,
            user_analytics=payload.userAnalytics,
            rag_context=rag_context,
            lang=payload.lang
        )

        return plan_json

    except PrioritizationGenerationError as e:
        logger.error("Prioritization generation failed after retries: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error("Unexpected failure in /prioritize: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error during prioritization")

@app.post("/api/v1/tasks/outcome")
async def register_outcome(payload: TaskOutcomePayload):
    register_task_outcome(payload)
    return {"status": "ok"}
