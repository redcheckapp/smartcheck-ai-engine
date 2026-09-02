import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from app.services.vector_store import query_context
from app.services.llm_engine import generate_prioritized_plan

# Configure logging for observability
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
        # Extract task titles to build the semantic search query. 
        # Fallback to 'titulo' ensures backward compatibility with the Spring Boot DTO.
        task_names = ", ".join([t.get("title", t.get("titulo", "")) for t in payload.tasks])
        
        # Retrieve historical context from local vector memory
        search_query = f"Previous execution performance related to: {task_names}"
        docs = query_context(payload.userId, search_query)
        rag_context = "\n".join(docs) if docs else ""
        
        # Generate the optimized JSON plan via Gemini
        plan_json = generate_prioritized_plan(
            tasks=payload.tasks,
            user_analytics=payload.userAnalytics,
            rag_context=rag_context,
            lang=payload.lang
        )
        
        return plan_json
        
    except ValueError as ve:
        logger.error("JSON parsing error during AI generation: %s", ve)
        raise HTTPException(status_code=502, detail="Invalid JSON response from AI provider")
    except Exception as e:
        logger.error("Prioritization engine failure: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error during prioritization")