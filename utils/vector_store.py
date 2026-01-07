"""
Vector Store - Chroma-based semantic memory for conversation history
Enables RAG (Retrieval Augmented Generation) for KOTO
Uses Gemini API for embeddings (lightweight alternative to sentence-transformers)
"""
import os
import sys
import json
import urllib.request
from datetime import datetime
from typing import List, Dict, Optional

# Lazy loading to avoid slow startup
_chroma_client = None
_collection = None

COLLECTION_NAME = "koto_conversations"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "chroma")
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')


class GeminiEmbeddingFunction:
    """Custom embedding function using Gemini API"""
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        if not GEMINI_API_KEY:
            # Fallback: return simple hash-based embeddings
            return [self._simple_embedding(text) for text in input]
        
        embeddings = []
        for text in input:
            try:
                embedding = self._get_gemini_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                print(f"Embedding error: {e}", file=sys.stderr)
                embeddings.append(self._simple_embedding(text))
        
        return embeddings
    
    def _get_gemini_embedding(self, text: str) -> List[float]:
        """Get embedding from Gemini API"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={GEMINI_API_KEY}"
        
        data = {
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": text[:2000]}]}  # Truncate to avoid token limits
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=10) as res:
            result = json.loads(res.read().decode('utf-8'))
            return result.get('embedding', {}).get('values', self._simple_embedding(text))
    
    def _simple_embedding(self, text: str) -> List[float]:
        """Fallback: Simple hash-based embedding (768 dimensions)"""
        import hashlib
        # Create a deterministic but simple embedding
        hash_bytes = hashlib.sha256(text.encode('utf-8')).digest() * 24  # 768 bytes
        return [b / 255.0 for b in hash_bytes[:768]]


def _get_collection():
    """Get or create Chroma collection (lazy load)"""
    global _chroma_client, _collection, _init_error
    
    if _collection is not None:
        return _collection
    
    try:
        import chromadb
        
        # Use EphemeralClient for serverless environments (Railway)
        # Data is in-memory and won't persist across restarts
        _chroma_client = chromadb.EphemeralClient()
        
        # Get or create collection with Gemini embedding function
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=GeminiEmbeddingFunction(),
            metadata={"description": "KOTO conversation history for RAG"}
        )
        
        return _collection
    except Exception as e:
        _init_error = str(e)
        print(f"Error initializing Chroma: {e}", file=sys.stderr)
        return None

# Store init error for debugging
_init_error = None


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
    global _init_error
    collection = _get_collection()
    if collection is None:
        return {"status": "not_initialized", "init_error": _init_error}
    
    try:
        count = collection.count()
        return {
            "status": "ok",
            "total_documents": count,
            "collection_name": COLLECTION_NAME
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
