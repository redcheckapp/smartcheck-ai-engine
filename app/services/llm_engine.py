import json
from datetime import datetime
from pathlib import Path
import google.generativeai as genai

from app.schemas import PrioritizationResponse

# Initialize the Gemini model with structured JSON output configuration
model = genai.GenerativeModel(
    model_name="models/gemini-2.5-flash",
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": PrioritizationResponse,
        "temperature": 0.6
    }
)

# Resolve prompt template path using pathlib for better cross-platform reliability
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROMPT_PATH = BASE_DIR / "prompts" / "smartcheck.txt"

# Pre-load the prompt template into memory during module initialization
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

def generate_prioritized_plan(tasks: list[dict], user_analytics: dict, rag_context: str, lang: str) -> dict:
    """
    Generates a prioritized execution plan using Gemini 2.5 Flash and RAG context.
    
    Args:
        tasks: List of pending tasks to be evaluated.
        user_analytics: User's historical data and profile metrics.
        rag_context: Formatted string containing similar past task executions.
        lang: Target language for the AI response support messages (e.g., 'es', 'en').
        
    Returns:
        Dictionary matching the PrioritizationResponse schema.
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Ensure a default English string if no RAG context is found
    fallback_context = rag_context if rag_context else "No historical context available."
    
    prompt = PROMPT_TEMPLATE.format(
        current_date=current_time,
        lang=lang,
        user_analytics=json.dumps(user_analytics, ensure_ascii=False),
        rag_context=fallback_context,
        tasks=json.dumps(tasks, ensure_ascii=False)
    )
    
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse AI response into JSON: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"AI prioritization generation failed: {str(e)}")