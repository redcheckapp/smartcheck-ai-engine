import os
import google.generativeai as genai
from schemas import PrioritizationResponse
import json

# Usamos gemini-1.5-flash o pro para soportar tipado fuerte con response_schema
model = genai.GenerativeModel(
    model_name="models/gemini-1.5-flash",
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": PrioritizationResponse,
        "temperature": 0.2
    }
)

def generate_prioritized_plan(tasks: list[dict], rag_context: str) -> dict:
    """Envía el contexto y las tareas a Gemini forzando el JSON de salida."""
    
    prompt = f"""
    Eres SmartCheck, un motor de inteligencia artificial especializado en productividad.
    Tu objetivo es analizar la lista de tareas pendientes y devolver un plan óptimo.
    
    Contexto histórico del rendimiento del usuario:
    {rag_context if rag_context else "Sin datos históricos relevantes."}
    
    Tareas pendientes a evaluar:
    {json.dumps(tasks, ensure_ascii=False)}
    
    Debes evaluar URGENCIA, ESFUERZO COGNITIVO e IMPACTO para decidir el 'ordenDefinido'.
    """
    
    response = model.generate_content(prompt)
    
    # El motor garantiza que response.text es un string JSON que cumple el esquema exacto
    return json.loads(response.text)