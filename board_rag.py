"""
RAG (Retrieval Augmented Generation) for Patient Board Data
Based on agent-2.9 faiss_rag.py implementation with FAISS
"""
import os
import json
import pickle
import hashlib
import logging
import httpx
import numpy as np
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from google import genai
from google.genai.types import EmbedContentConfig
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag")

# Configuration
PROJECT_ID = os.getenv("PROJECT_ID", "medforce-pilot-backend")
PROJECT_LOCATION = os.getenv("PROJECT_LOCATION", "us-central1")
EMBEDDING_MODEL = "text-embedding-005"
EMBEDDING_DIM = 768
CACHE_FILE = "vector_cache/embedding_cache.pkl"
BOARD_BASE_URL = "https://iso-clinic-v3.vercel.app"
BOARD_API_BASE = f"{BOARD_BASE_URL}/api"

# Initialize Gemini client
client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=PROJECT_LOCATION
)

# Global cache
_embedding_cache: Dict[str, List[float]] = {}
_faiss_index: Optional[FAISS] = None


async def load_board_items(patient_id: str) -> List[Dict[str, Any]]:
    """
    Load board items from API.
    Based on agent-2.9 canvas_ops.py get_board_items functionality.
    
    Args:
        patient_id: Patient ID
        
    Returns:
        List of board items
    """
    try:
        logger.info(f"Loading board items for patient {patient_id}")
        
        async with httpx.AsyncClient() as client_http:
            response = await client_http.get(
                f"{BOARD_API_BASE}/board-items/{patient_id.lower()}",
                timeout=15.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle new API format
                if isinstance(data, dict) and 'items' in data:
                    items = data['items']
                else:
                    items = data if isinstance(data, list) else []
                
                logger.info(f"Loaded {len(items)} board items")
                return items
            else:
                logger.error(f"Failed to load board items: HTTP {response.status_code}")
                return []
                
    except Exception as e:
        logger.error(f"Error loading board items: {e}")
        return []


def load_cache() -> Dict[str, List[float]]:
    """Load embedding cache from disk."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                cache = pickle.load(f)
            logger.info(f"Loaded {len(cache)} cached embeddings")
            return cache
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return {}
    return {}


def save_cache(cache: Dict[str, List[float]]) -> None:
    """Save embedding cache to disk."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(cache, f)
        logger.info(f"Saved {len(cache)} embeddings to cache")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")


def get_object_id(obj: Dict[str, Any]) -> str:
    """Get unique ID for an object."""
    return obj.get("id") or obj.get("object_id") or str(hash(json.dumps(obj, sort_keys=True)))


def extract_text_recursive(obj: Any, parent_key: str = "") -> List[str]:
    """Recursively extract text from nested dictionaries and lists."""
    texts = []
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ["id", "x", "y", "width", "height", "rotation", "createdAt", "updatedAt"]:
                continue
            if isinstance(value, (str, int, float, bool)):
                if value and str(value).strip():
                    texts.append(f"{key}: {value}")
            elif isinstance(value, (dict, list)):
                texts.extend(extract_text_recursive(value, key))
    
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                texts.extend(extract_text_recursive(item, parent_key))
            elif item and str(item).strip():
                texts.append(str(item))
    
    return texts


def extract_searchable_text(item: Dict[str, Any]) -> str:
    """Extract searchable text from a board item."""
    text_parts = extract_text_recursive(item)
    return " | ".join(text_parts)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed multiple texts using Gemini embedding model.
    Based on agent-2.9 faiss_rag.py embed_texts functionality.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors
    """
    try:
        embeddings = []
        for text in texts:
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIM
                )
            )
            
            if result and result.embeddings:
                embeddings.append(result.embeddings[0].values)
            else:
                # Use zero vector as fallback
                embeddings.append([0.0] * EMBEDDING_DIM)
        
        return embeddings
        
    except Exception as e:
        logger.error(f"Error embedding texts: {e}")
        # Return zero vectors as fallback
        return [[0.0] * EMBEDDING_DIM for _ in texts]


def rag_object(json_data: List[Dict[str, Any]], query: str, k: int = 10) -> List[Dict[str, Any]]:
    """
    Select relevant objects using FAISS and cached embeddings.
    Based on agent-2.9 faiss_rag.py rag_object functionality.
    
    Args:
        json_data: List of board items
        query: Search query
        k: Number of results to return
        
    Returns:
        List of relevant board items
    """
    try:
        if not json_data:
            logger.warning("No data provided for RAG")
            return []
        
        # Load cache
        cache = load_cache()
        docs = []
        embeddings = []
        new_objects = 0
        
        for obj in json_data:
            obj_id = get_object_id(obj)
            text = extract_searchable_text(obj)
            
            if not text or len(text.strip()) < 10:
                continue
            
            # Check cache
            if obj_id in cache:
                embedding = cache[obj_id]
            else:
                # Generate new embedding
                embedding = embed_texts([text])[0]
                cache[obj_id] = embedding
                new_objects += 1
            
            docs.append(Document(page_content=text, metadata=obj))
            embeddings.append(embedding)
        
        # Save cache if new embeddings
        if new_objects > 0:
            save_cache(cache)
        
        logger.info(f"🔹 Total: {len(json_data)} | 🆕 New: {new_objects} | ⚡ Cached: {len(json_data) - new_objects}")
        
        if not docs:
            return []
        
        # Build FAISS index
        emb_array = np.array(embeddings)
        text_embeddings = [(doc.page_content, emb.tolist()) for doc, emb in zip(docs, emb_array)]
        
        index = FAISS.from_embeddings(
            text_embeddings=text_embeddings,
            embedding=client  # Pass client as embedding function
        )
        
        # Search
        query_embedding = embed_texts([query])[0]
        search_results = index.similarity_search_by_vector(query_embedding, k=k)
        
        # Extract objects from metadata
        result_obj = []
        for res in search_results:
            if res.metadata:
                result_obj.append(res.metadata)
            else:
                try:
                    result_obj.append(json.loads(res.page_content))
                except:
                    pass
        
        logger.info(f"Found {len(result_obj)} relevant items")
        return result_obj
        
    except Exception as e:
        logger.error(f"Error in RAG object: {e}")
        return []


async def run_rag(patient_id: str, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Run RAG query and return items.
    Based on agent-2.9 faiss_rag.py run_rag functionality.
    
    Args:
        patient_id: Patient ID
        query: Search query
        top_k: Number of results
        
    Returns:
        List of relevant board items
    """
    try:
        logger.info(f"Running RAG for query: {query[:100]}")
        
        # Load board items
        board_items = await load_board_items(patient_id)
        
        if not board_items:
            logger.warning("No board items available")
            return []
        
        # Run RAG with FAISS
        results = rag_object(board_items, query, k=top_k)
        
        logger.info(f"RAG returned {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"Error in run_rag: {e}")
        return []

