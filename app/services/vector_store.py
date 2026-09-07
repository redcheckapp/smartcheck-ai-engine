import os
from datetime import datetime
from typing import Optional
import chromadb
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Inicializa ChromaDB guardando los vectores en la carpeta local ./chroma_data
chroma_client = chromadb.PersistentClient(path="./chroma_data")

# hnsw:space debe fijarse explícitamente: Chroma usa L2 al cuadrado por defecto,
# no coseno, si no se indica. Solo se aplica al CREAR la colección — si ya existe
# con otra métrica, get_or_create_collection la ignora en silencio.
_COSINE_SPACE = {"hnsw:space": "cosine"}

# Colección 1: registros individuales de resultados de tareas (una entrada por tarea).
task_outcomes_collection = chroma_client.get_or_create_collection(name="task_outcomes", metadata=_COSINE_SPACE)
# Colección 2: patrón agregado por usuario+asignatura (una entrada por asignatura, se actualiza, no crece).
user_patterns_collection = chroma_client.get_or_create_collection(name="user_patterns", metadata=_COSINE_SPACE)

# Retrieval híbrido para query_task_outcomes: se piden más candidatos de los que
# hacen falta por similitud semántica, y se re-rankean combinando similitud,
# recencia y coincidencia de asignatura, en vez de fiarse solo del orden de Chroma.
CANDIDATE_POOL_SIZE = 8
RECENCY_HALF_LIFE_DAYS = 30
WEIGHT_SEMANTIC = 0.6
WEIGHT_RECENCY = 0.25
WEIGHT_SUBJECT_MATCH = 0.15


def get_embedding(text: str) -> list[float]:
    """Llama a Google para convertir el texto en un vector denso."""
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text,
        task_type="retrieval_document"
    )
    return result['embedding']


def _upsert(collection, doc_id: str, user_id: str, context_text: str, metadata: dict):
    vector = get_embedding(context_text)
    metadata = {**metadata, "userId": user_id}
    collection.upsert(
        ids=[doc_id],
        embeddings=[vector],
        documents=[context_text],
        metadatas=[metadata]
    )


def upsert_task_outcome(task_id: str, user_id: str, context_text: str, metadata: dict):
    """Guarda el resultado de una tarea individual en la colección de histórico."""
    _upsert(task_outcomes_collection, task_id, user_id, context_text, metadata)


def upsert_user_pattern(pattern_id: str, user_id: str, context_text: str, metadata: dict):
    """Guarda/actualiza el patrón agregado de una asignatura (mismo id -> sobrescribe, no acumula)."""
    _upsert(user_patterns_collection, pattern_id, user_id, context_text, metadata)


def get_task_outcomes(user_id: str, asignatura: str) -> dict:
    """Recupera TODOS los resultados de tareas de un usuario para una asignatura.

    A diferencia de query_task_outcomes, esto no es una búsqueda semántica: se usa
    para agregar estadísticas (ver pattern_service.py), así que necesita el conjunto
    completo, no solo los k más parecidos.
    """
    try:
        return task_outcomes_collection.get(
            where={"$and": [{"userId": user_id}, {"asignatura": asignatura}]}
        )
    except Exception as e:
        print(f"Aviso: No se pudo leer el histórico de tareas para agregación ({e}).")
        return {"documents": [], "metadatas": []}


def _semantic_similarity(distance: float) -> float:
    """En espacio coseno, Chroma devuelve distance = 1 - similitud_coseno."""
    return max(0.0, 1.0 - distance)


def _recency_score(fecha_iso: Optional[str]) -> float:
    """Decaimiento suave: 1.0 si es de hoy, 0.5 a los RECENCY_HALF_LIFE_DAYS días, etc."""
    if not fecha_iso:
        return 0.0
    try:
        fecha = datetime.fromisoformat(fecha_iso)
    except ValueError:
        return 0.0
    dias = max((datetime.now() - fecha).days, 0)
    return 1.0 / (1.0 + dias / RECENCY_HALF_LIFE_DAYS)


def query_task_outcomes(user_id: str, query_text: str, asignaturas: Optional[list[str]] = None, n_results: int = 3) -> list[str]:
    """Busca tareas históricas relevantes con retrieval híbrido.

    Se piden CANDIDATE_POOL_SIZE candidatos por similitud semántica (filtrados
    solo por userId, sin restringir por asignatura, para no perder señal
    relevante entre asignaturas), y se re-rankean combinando similitud
    semántica, recencia (más reciente = más predictivo del comportamiento
    actual) y coincidencia de asignatura con las tareas de hoy — en vez de
    devolver directamente el top-k de Chroma.
    """
    asignaturas = asignaturas or []
    try:
        query_vector = get_embedding(query_text)
        results = task_outcomes_collection.query(
            query_embeddings=[query_vector],
            n_results=CANDIDATE_POOL_SIZE,
            where={"userId": user_id},  # Filtro estricto de seguridad
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        print(f"Aviso: No se pudo recuperar el historial de tareas ({e}). Continuando sin él.")
        return []

    documentos = (results.get("documents") or [[]])[0]
    if not documentos:
        return []
    metadatas = (results.get("metadatas") or [[]])[0]
    distancias = (results.get("distances") or [[]])[0]

    candidatos = []
    for doc, meta, dist in zip(documentos, metadatas, distancias):
        semantica = _semantic_similarity(dist)
        recencia = _recency_score(meta.get("fechaCompletado") or meta.get("fechaLimite"))
        coincide_asignatura = 1.0 if meta.get("asignatura") in asignaturas else 0.0

        puntuacion = (
            semantica * WEIGHT_SEMANTIC
            + recencia * WEIGHT_RECENCY
            + coincide_asignatura * WEIGHT_SUBJECT_MATCH
        )
        candidatos.append((puntuacion, doc))

    candidatos.sort(key=lambda c: c[0], reverse=True)
    return [doc for _, doc in candidatos[:n_results]]


def query_user_patterns(user_id: str, asignaturas: list[str]) -> list[str]:
    """Recupera los patrones agregados de las asignaturas relevantes.

    Lookup exacto por metadatos (no búsqueda semántica): solo hay una entrada por
    asignatura, así que no tiene sentido rankear por similitud — se pide
    directamente la de cada asignatura que aparece en las tareas de hoy.
    """
    if not asignaturas:
        return []
    try:
        results = user_patterns_collection.get(
            where={"$and": [{"userId": user_id}, {"asignatura": {"$in": asignaturas}}]}
        )
        return results.get("documents") or []
    except Exception as e:
        print(f"Aviso: No se pudieron recuperar los patrones de usuario ({e}). Continuando sin ellos.")
        return []


def build_rag_context(user_id: str, query_text: str, asignaturas: list[str]) -> str:
    """Sintetiza el contexto RAG combinando histórico de tareas similares y patrones agregados."""
    secciones = []

    tareas_similares = query_task_outcomes(user_id, query_text, asignaturas=asignaturas)
    if tareas_similares:
        secciones.append("Historial de tareas similares:\n" + "\n".join(tareas_similares))

    patrones = query_user_patterns(user_id, asignaturas)
    if patrones:
        secciones.append("Patrones de rendimiento por asignatura:\n" + "\n".join(patrones))

    return "\n\n".join(secciones)
