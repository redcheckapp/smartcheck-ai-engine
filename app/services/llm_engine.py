import json
import os
import time
from datetime import datetime
import google.generativeai as genai
from pydantic import ValidationError
from app.schemas import PrioritizationResponse

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1.5

model = genai.GenerativeModel(
    model_name="models/gemini-2.5-flash",
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": PrioritizationResponse,
        "temperature": 0.6
    }
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "smartcheck.txt")
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()


class PrioritizationGenerationError(Exception):
    """Raised when Gemini fails to produce a schema-valid plan after all retries."""


def generate_prioritized_plan(tasks: list[dict], user_analytics: dict, rag_context: str, lang: str) -> dict:

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    prompt = PROMPT_TEMPLATE.format(
        current_date=ahora,
        lang=lang,
        user_analytics=json.dumps(user_analytics, ensure_ascii=False),
        rag_context=rag_context if rag_context else "Sin historial específico previo.",
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
            print(f"Aviso: intento {attempt}/{MAX_ATTEMPTS} de generar el plan falló ({e}).")
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)

    raise PrioritizationGenerationError(
        f"Gemini no devolvió un plan con schema válido tras {MAX_ATTEMPTS} intentos: {last_error}"
    )