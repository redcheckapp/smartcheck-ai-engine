import json
import logging
import time
from datetime import datetime
from pathlib import Path
import google.generativeai as genai
from app.schemas import PrioritizationResponse

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1.5

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


class PrioritizationGenerationError(Exception):
    """Raised when Gemini fails to produce a schema-valid plan after all retries."""


def generate_prioritized_plan(tasks: list[dict], user_analytics: dict, rag_context: str, lang: str) -> dict:
    """
    Generates a prioritized execution plan using Gemini 2.5 Flash and RAG context.

    Args:
        tasks: List of pending tasks to be evaluated (already feature-enriched).
        user_analytics: User's historical data and profile metrics.
        rag_context: Formatted string containing similar past task executions.
        lang: Target language for the AI response support messages (e.g., 'es', 'en').

    Returns:
        Dictionary matching the PrioritizationResponse schema.

    Raises:
        PrioritizationGenerationError: if Gemini doesn't produce a schema-valid
            response after MAX_ATTEMPTS tries.
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Ensure a default string if no RAG context is found
    fallback_context = rag_context if rag_context else "No historical context available."

    prompt = PROMPT_TEMPLATE.format(
        current_date=current_time,
        lang=lang,
        user_analytics=json.dumps(user_analytics, ensure_ascii=False),
        rag_context=fallback_context,
        tasks=json.dumps(tasks, ensure_ascii=False)
    )

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = model.generate_content(prompt)
            data = json.loads(response.text)
            # response_schema constrains Gemini's output, but doesn't guarantee it on
            # our side — validate explicitly rather than trusting it blindly.
            validated = PrioritizationResponse.model_validate(data)
            return validated.model_dump()
        except Exception as e:
            last_error = e
            logger.warning("Attempt %d/%d to generate the plan failed (%s).", attempt, MAX_ATTEMPTS, e)
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)

    raise PrioritizationGenerationError(
        f"Gemini did not return a schema-valid plan after {MAX_ATTEMPTS} attempts: {last_error}"
    )
