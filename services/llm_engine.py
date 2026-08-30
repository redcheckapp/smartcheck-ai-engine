import json
import google.generativeai as genai
from schemas import PrioritizationResponse
import os

model = genai.GenerativeModel(
    model_name="models/gemini-1.5-flash",
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": PrioritizationResponse,
        "temperature": 0.2
    }
)

def generate_prioritized_plan(tasks: list[dict], user_analytics: dict, rag_context: str) -> dict:
    """Ensambla el prompt con las 4 dimensiones y lanza la consulta al LLM."""
    
    prompt = f"""
    Eres SmartCheck, un motor de inteligencia artificial especializado en productividad y gestión del tiempo.
    Tu objetivo es analizar la lista de tareas pendientes del usuario y devolver un plan de ejecución óptimo.
    
    Para determinar el 'ordenDefinido', debes evaluar y combinar internamente estas 4 dimensiones:
    1. ESFUERZO COGNITIVO: Analiza la complejidad técnica o mental del título. Tareas densas deben ir primero.
    2. DEPENDENCIAS IMPLÍCITAS: Busca bloqueos lógicos (ej. Configurar la base de datos va antes que programar la API).
    3. IMPACTO (Matriz Eisenhower): Palabras clave como 'Examen', 'Defensa', 'Producción' o 'Despliegue' multiplican la prioridad.
    4. BALANCE DE ASIGNATURAS: El usuario tiende a retrasarse en asignaturas con menor progreso. Empuja hacia arriba las tareas de asignaturas más abandonadas.

    --- CONTEXTO ANALÍTICO ---
    Progreso actual por asignatura:
    {json.dumps(user_analytics, ensure_ascii=False)}

    Memoria Histórica de Rendimiento (Contexto RAG):
    {rag_context if rag_context else "Sin historial específico previo."}

    --- TAREAS PENDIENTES ---
    {json.dumps(tasks, ensure_ascii=False)}
    """
    
    response = model.generate_content(prompt)
    return json.loads(response.text)