"""
Vector Store - Chroma-based semantic memory for conversation history
Enables RAG (Retrieval Augmented Generation) for KOTO
"""
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional

# Lazy loading to avoid slow startup
_chroma_client = None
_collection = None
_embedding_function = None

COLLECTION_NAME = "koto_conversations"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "chroma")


def _get_embedding_function():
    """Get or create embedding function (lazy load)"""
    global _embedding_function
    if _embedding_function is None:
        try:
            from chromadb.utils import embedding_functions
            # Use sentence-transformers with a multilingual model for Japanese
            _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="paraphrase-multilingual-MiniLM-L12-v2"
            )
        except Exception as e:
            print(f"Warning: Could not load embedding function: {e}", file=sys.stderr)
            return None
    return _embedding_function


def _get_collection():
    """Get or create Chroma collection (lazy load)"""
    global _chroma_client, _collection
    
    if _collection is not None:
        return _collection
    
    try:
        import chromadb
        from chromadb.config import Settings
        
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # Create persistent client
        _chroma_client = chromadb.PersistentClient(
            path=DATA_DIR,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection with embedding function
        ef = _get_embedding_function()
        if ef:
            _collection = _chroma_client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=ef,
                metadata={"description": "KOTO conversation history for RAG"}
            )
        else:
            # Fallback without custom embedding
            _collection = _chroma_client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "KOTO conversation history for RAG"}
            )
        
        return _collection
    except Exception as e:
        print(f"Error initializing Chroma: {e}", file=sys.stderr)
        return None


def save_conversation(user_id: str, role: str, text: str, metadata: Optional[Dict] = None) -> bool:
    """
    Save a conversation message to the vector store
    
    Args:
        user_id: LINE user ID
        role: 'user' or 'model'
        text: Message content
        metadata: Optional additional metadata
    
    Returns:
        True if saved successfully, False otherwise
    """
    collection = _get_collection()
    if collection is None:
        return False
    
    try:
        # Create unique ID
        doc_id = f"{user_id}_{datetime.now().isoformat()}_{role}"
        
        # Prepare metadata
        doc_metadata = {
            "user_id": user_id,
            "role": role,
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            doc_metadata.update(metadata)
        
        # Add to collection
        collection.add(
            documents=[text],
            metadatas=[doc_metadata],
            ids=[doc_id]
        )
        
        return True
    except Exception as e:
        print(f"Error saving to vector store: {e}", file=sys.stderr)
        return False


def search_relevant_context(user_id: str, query: str, n_results: int = 5) -> List[Dict]:
    """
    Search for relevant past conversations
    
    Args:
        user_id: LINE user ID (for filtering)
        query: Search query (current user message)
        n_results: Number of results to return
    
    Returns:
        List of relevant past messages with metadata
    """
    collection = _get_collection()
    if collection is None:
        return []
    
    try:
        # Search with user filter
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_id": user_id}
        )
        
        # Format results
        relevant_context = []
        if results and results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results.get('distances') else None
                
                relevant_context.append({
                    "text": doc,
                    "role": metadata.get("role", "unknown"),
                    "timestamp": metadata.get("timestamp", ""),
                    "relevance": 1 - (distance or 0) if distance else 1  # Convert distance to similarity
                })
        
        return relevant_context
    except Exception as e:
        print(f"Error searching vector store: {e}", file=sys.stderr)
        return []


def get_context_summary(user_id: str, query: str, max_tokens: int = 500) -> str:
    """
    Get a formatted summary of relevant past context for injection into AI prompt
    
    Args:
        user_id: LINE user ID
        query: Current user query
        max_tokens: Approximate maximum length of summary
    
    Returns:
        Formatted context string for AI prompt
    """
    relevant = search_relevant_context(user_id, query, n_results=5)
    
    if not relevant:
        return ""
    
    # Build context summary
    context_parts = []
    total_chars = 0
    max_chars = max_tokens * 3  # Rough estimate for Japanese
    
    for item in relevant:
        if total_chars >= max_chars:
            break
        
        role_label = "ユーザー" if item["role"] == "user" else "KOTO"
        text = item["text"][:200]  # Truncate long messages
        
        entry = f"[{role_label}] {text}"
        context_parts.append(entry)
        total_chars += len(entry)
    
    if context_parts:
        return "【過去の関連会話】\n" + "\n".join(context_parts) + "\n"
    
    return ""


def get_collection_stats() -> Dict:
    """Get statistics about the vector store"""
    collection = _get_collection()
    if collection is None:
        return {"status": "not_initialized"}
    
    try:
        count = collection.count()
        return {
            "status": "ok",
            "total_documents": count,
            "collection_name": COLLECTION_NAME
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
