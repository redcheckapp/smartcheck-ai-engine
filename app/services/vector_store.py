import os
import chromadb
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Inicializa ChromaDB guardando los vectores en la carpeta local ./chroma_data
chroma_client = chromadb.PersistentClient(path="./chroma_data")
collection = chroma_client.get_or_create_collection(name="user_tasks_history")

def get_embedding(text: str) -> list[float]:
    """Llama a Google para convertir el texto en un vector denso."""
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text,
        task_type="retrieval_document"
    )
    return result['embedding']

def upsert_task(task_id: str, user_id: str, context_text: str, metadata: dict):
    """Genera el vector y lo guarda en ChromaDB con metadatos asociados."""
    vector = get_embedding(context_text)
    
    # Inyectamos el userId para poder filtrar luego
    metadata["userId"] = user_id 
    
    collection.upsert(
        ids=[task_id],
        embeddings=[vector],
        documents=[context_text],
        metadatas=[metadata]
    )

def query_context(user_id: str, query_text: str, n_results: int = 3) -> list[str]:
    """Busca en el historial del usuario usando similitud del coseno."""
    try:
        query_vector = get_embedding(query_text)
        
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            where={"userId": user_id} # Filtro estricto de seguridad
        )
        
        # Devuelve los fragmentos de texto más relevantes
        return results['documents'][0] if results['documents'] else []
    except Exception as e:
        print(f"Aviso: No se pudo recuperar el contexto RAG ({e}). Continuando sin historial vectorial.")
        return []