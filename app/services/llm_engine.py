import json
import os
from datetime import datetime
import google.generativeai as genai
from app.schemas import PrioritizationResponse

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

def generate_prioritized_plan(tasks: list[dict], user_analytics: dict, rag_context: str, lang: str) -> dict:
    
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    prompt = PROMPT_TEMPLATE.format(
        current_date=ahora,
        lang=lang,
        user_analytics=json.dumps(user_analytics, ensure_ascii=False),
        rag_context=rag_context if rag_context else "Sin historial específico previo.",
        tasks=json.dumps(tasks, ensure_ascii=False)
    )
    
    response = model.generate_content(prompt)
    return json.loads(response.text)