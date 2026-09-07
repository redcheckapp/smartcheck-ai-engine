import os
import logging
from datetime import datetime
from typing import Optional
import chromadb
import google.generativeai as genai
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize ChromaDB with local persistent storage
chroma_client = chromadb.PersistentClient(path="./chroma_data")

# hnsw:space must be set explicitly: Chroma defaults to squared L2 distance,
# not cosine, when it's omitted. Only takes effect when the collection is
# first CREATED — if it already exists, get_or_create_collection ignores it.
_COSINE_SPACE = {"hnsw:space": "cosine"}

# Collection 1: individual task-outcome records (one entry per task).
task_outcomes_collection = chroma_client.get_or_create_collection(name="task_outcomes", metadata=_COSINE_SPACE)
# Collection 2: aggregated pattern per user+subject (one entry per subject, updated in place, not appended).
user_patterns_collection = chroma_client.get_or_create_collection(name="user_patterns", metadata=_COSINE_SPACE)

# Hybrid retrieval for query_task_outcomes: pull more candidates than needed by
# semantic similarity, then re-rank combining similarity, recency, and subject
# match, instead of trusting Chroma's raw top-k order.
CANDIDATE_POOL_SIZE = 8
RECENCY_HALF_LIFE_DAYS = 30
WEIGHT_SEMANTIC = 0.6
WEIGHT_RECENCY = 0.25
WEIGHT_SUBJECT_MATCH = 0.15


def get_embedding(text: str) -> list[float]:
    """
    Calls the Google Gemini API to generate a dense vector embedding for the given text.
    """
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text,
        task_type="retrieval_document"
    )
    return result['embedding']


def _upsert(collection, doc_id: str, user_id: str, context_text: str, metadata: dict) -> None:
    vector = get_embedding(context_text)
    # Inject userId to enforce tenant isolation during retrieval.
    metadata = {**metadata, "userId": user_id}
    collection.upsert(
        ids=[doc_id],
        embeddings=[vector],
        documents=[context_text],
        metadatas=[metadata]
    )


def upsert_task_outcome(task_id: str, user_id: str, context_text: str, metadata: dict) -> None:
    """Stores an individual task outcome in the historical collection."""
    _upsert(task_outcomes_collection, task_id, user_id, context_text, metadata)


def upsert_user_pattern(pattern_id: str, user_id: str, context_text: str, metadata: dict) -> None:
    """Stores/updates a subject's aggregated pattern (same id -> overwrites, doesn't accumulate)."""
    _upsert(user_patterns_collection, pattern_id, user_id, context_text, metadata)


def get_task_outcomes(user_id: str, asignatura: str) -> dict:
    """Retrieves ALL task outcomes for a user in a given subject.

    Unlike query_task_outcomes, this is not a semantic search: it's used to
    aggregate statistics (see pattern_service.py), so it needs the full set,
    not just the k nearest neighbors.
    """
    try:
        return task_outcomes_collection.get(
            where={"$and": [{"userId": user_id}, {"asignatura": asignatura}]}
        )
    except Exception as e:
        logger.warning("Could not read task history for aggregation (%s).", e)
        return {"documents": [], "metadatas": []}


def _semantic_similarity(distance: float) -> float:
    """In cosine space, Chroma returns distance = 1 - cosine_similarity."""
    return max(0.0, 1.0 - distance)


def _recency_score(fecha_iso: Optional[str]) -> float:
    """Smooth decay: 1.0 if today, 0.5 at RECENCY_HALF_LIFE_DAYS days, etc."""
    if not fecha_iso:
        return 0.0
    try:
        fecha = datetime.fromisoformat(fecha_iso)
    except ValueError:
        return 0.0
    dias = max((datetime.now() - fecha).days, 0)
    return 1.0 / (1.0 + dias / RECENCY_HALF_LIFE_DAYS)


def query_task_outcomes(user_id: str, query_text: str, asignaturas: Optional[list[str]] = None, n_results: int = 3) -> list[str]:
    """Searches for relevant historical tasks using hybrid retrieval.

    Pulls CANDIDATE_POOL_SIZE candidates by semantic similarity (filtered only
    by userId, without restricting by subject, so as not to lose relevant
    cross-subject signal), then re-ranks combining semantic similarity,
    recency (more recent = more predictive of current behavior), and subject
    match against today's tasks — instead of returning Chroma's raw top-k.
    """
    asignaturas = asignaturas or []
    try:
        query_vector = get_embedding(query_text)
        results = task_outcomes_collection.query(
            query_embeddings=[query_vector],
            n_results=CANDIDATE_POOL_SIZE,
            where={"userId": user_id},  # Strict tenant isolation filter
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        logger.warning("Could not retrieve task history (%s). Continuing without it.", e)
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
    """Retrieves the aggregated patterns for the relevant subjects.

    Exact metadata lookup (not semantic): there's only one entry per subject,
    so ranking by similarity would be meaningless — the pattern for each
    subject appearing in today's tasks is fetched directly.
    """
    if not asignaturas:
        return []
    try:
        results = user_patterns_collection.get(
            where={"$and": [{"userId": user_id}, {"asignatura": {"$in": asignaturas}}]}
        )
        return results.get("documents") or []
    except Exception as e:
        logger.warning("Could not retrieve user patterns (%s). Continuing without them.", e)
        return []


def build_rag_context(user_id: str, query_text: str, asignaturas: list[str]) -> str:
    """Synthesizes the RAG context combining similar task history and aggregated patterns."""
    secciones = []

    tareas_similares = query_task_outcomes(user_id, query_text, asignaturas=asignaturas)
    if tareas_similares:
        secciones.append("Historial de tareas similares:\n" + "\n".join(tareas_similares))

    patrones = query_user_patterns(user_id, asignaturas)
    if patrones:
        secciones.append("Patrones de rendimiento por asignatura:\n" + "\n".join(patrones))

    return "\n\n".join(secciones)
