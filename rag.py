"""
RAG Module - Simple wrapper around board_rag.py
Provides synchronous interface for chat_model.py
"""
import asyncio
from board_rag import run_rag as async_run_rag
from patient_manager import patient_manager


def run_rag(query: str, patient_id: str = None, top_k: int = 3):
    """
    Run RAG query synchronously.
    
    Args:
        query: Search query
        patient_id: Patient ID (defaults to current patient)
        top_k: Number of results to return
        
    Returns:
        List of relevant documents/context
    """
    if patient_id is None:
        patient_id = patient_manager.get_patient_id()
    
    # Run async function synchronously
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(async_run_rag(patient_id, query, top_k))
        return result
    except Exception as e:
        print(f"RAG error: {e}")
        return []
