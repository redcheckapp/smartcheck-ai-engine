import os
import logging
import chromadb
import google.generativeai as genai
from dotenv import load_dotenv

# Configure logging for professional error tracking
logger = logging.getLogger(__name__)

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize ChromaDB with local persistent storage
chroma_client = chromadb.PersistentClient(path="./chroma_data")
collection = chroma_client.get_or_create_collection(name="user_tasks_history")

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

def upsert_task(task_id: str, user_id: str, context_text: str, metadata: dict) -> None:
    """
    Generates the vector embedding and upserts it into ChromaDB with associated metadata.
    """
    vector = get_embedding(context_text)
    
    # Inject userId to enforce tenant isolation during retrieval
    metadata["userId"] = user_id 
    
    collection.upsert(
        ids=[task_id],
        embeddings=[vector],
        documents=[context_text],
        metadatas=[metadata]
    )

def query_context(user_id: str, query_text: str, n_results: int = 3) -> list[str]:
    """
    Searches the user's historical execution data using cosine similarity.
    """
    try:
        query_vector = get_embedding(query_text)
        
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            where={"userId": user_id} # Strict tenant isolation filter
        )
        
        # Return the most relevant document chunks
        return results['documents'][0] if results['documents'] else []
    except Exception as e:
        logger.warning("RAG context retrieval failed (%s). Proceeding without vector history.", e)
        return []