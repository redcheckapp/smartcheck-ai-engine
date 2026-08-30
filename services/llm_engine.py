import json
import os
import google.generativeai as genai
from schemas import PrioritizationResponse

model = genai.GenerativeModel(
    model_name="models/gemini-1.5-flash",
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": PrioritizationResponse,
        "temperature": 0.2
    }
)

# Cargar la plantilla en memoria una sola vez al inicio
PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "smartcheck.txt")
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

def generate_prioritized_plan(tasks: list[dict], user_analytics: dict, rag_context: str) -> dict:
    """Ensambla el prompt leyendo la plantilla e inyectando las 4 dimensiones."""
    
    # Inyectar los datos reales reemplazando las llaves en el archivo de texto
    prompt = PROMPT_TEMPLATE.format(
        user_analytics=json.dumps(user_analytics, ensure_ascii=False),
        rag_context=rag_context if rag_context else "Sin historial específico previo.",
        tasks=json.dumps(tasks, ensure_ascii=False)
    )
    
    response = model.generate_content(prompt)
    return json.loads(response.text)