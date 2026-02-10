"""
Vector Memory Store using Qdrant (Gemini Embeddings)
Handles semantic search over memories for Clawdbot
"""
import os
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.secrets")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("⚠️ Qdrant not available. Using fallback keyword search.")

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("⚠️ Google Generative AI not available. Embeddings disabled.")

# ============================================================================
# Configuration
# ============================================================================

QDRANT_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "qdrant_data"
COLLECTION_NAME = "clawdbot_memories"
EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIM = 768

# Configure GenAI
api_key = os.getenv("GEMINI_API_KEY")
if GENAI_AVAILABLE and api_key:
    genai.configure(api_key=api_key)
else:
    print("⚠️ Gemini API Key missing or lib not installed.")

# ============================================================================
# Vector Store
# ============================================================================

class VectorMemoryStore:
    """Semantic memory store using Qdrant."""
    
    def __init__(self):
        self.client = None
        self.initialized = False
        
        if QDRANT_AVAILABLE:
            try:
                QDRANT_PATH.mkdir(parents=True, exist_ok=True)
                self.client = QdrantClient(path=str(QDRANT_PATH))
                self._ensure_collection()
                self.initialized = True
                print(f"✅ Vector store initialized at {QDRANT_PATH}")
            except Exception as e:
                print(f"⚠️ Qdrant init failed: {e}")
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        
        if not exists:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE
                )
            )
            print(f"✅ Created collection: {COLLECTION_NAME}")
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding vector for text using Gemini."""
        if not GENAI_AVAILABLE or not os.getenv("GEMINI_API_KEY"):
            return None
        
        try:
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"⚠️ Embedding failed: {e}")
            return None
    
    def add_memory(
        self,
        memory_id: str,
        profile_id: str,
        content: str,
        memory_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a memory to the vector store."""
        if not self.initialized:
            return False
        
        embedding = self._get_embedding(content)
        if not embedding:
            return False
        
        point = PointStruct(
            id=hash(memory_id) % (10**18),  # Convert UUID to int
            vector=embedding,
            payload={
                "memory_id": memory_id,
                "profile_id": profile_id,
                "content": content,
                "type": memory_type,
                "created_at": datetime.now().isoformat(),
                **(metadata or {})
            }
        )
        
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[point]
        )
        return True
    
    def search(
        self,
        query: str,
        profile_id: Optional[str] = None,
        limit: int = 5,
        score_threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """Search for relevant memories."""
        if not self.initialized:
            return []
        
        embedding = self._get_embedding(query)
        if not embedding:
            return []
        
        # Build filter
        filter_conditions = None
        if profile_id:
            filter_conditions = Filter(
                must=[
                    FieldCondition(
                        key="profile_id",
                        match=MatchValue(value=profile_id)
                    )
                ]
            )
        
        try:
            results = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=embedding,
                query_filter=filter_conditions,
                limit=limit,
                score_threshold=score_threshold
            )
            
            return [
                {
                    "content": r.payload.get("content"),
                    "profile_id": r.payload.get("profile_id"),
                    "type": r.payload.get("type"),
                    "score": r.score,
                    "memory_id": r.payload.get("memory_id")
                }
                for r in results.points
            ]
        except Exception as e:
            print(f"⚠️ Search failed: {e}")
            return []
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        if not self.initialized:
            return False
        
        try:
            self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=[hash(memory_id) % (10**18)]
            )
            return True
        except:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        if not self.initialized:
            return {"status": "not_initialized"}
        
        try:
            info = self.client.get_collection(COLLECTION_NAME)
            return {
                "status": "initialized",
                "points_count": info.points_count,
                "indexed_vectors_count": getattr(info, 'indexed_vectors_count', info.points_count)
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ============================================================================
# Fallback: Keyword Search
# ============================================================================

class KeywordMemoryStore:
    """Simple keyword-based memory search fallback."""
    
    def __init__(self):
        self.memories: Dict[str, Dict] = {}
    
    def add_memory(
        self,
        memory_id: str,
        profile_id: str,
        content: str,
        memory_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        self.memories[memory_id] = {
            "memory_id": memory_id,
            "profile_id": profile_id,
            "content": content,
            "type": memory_type,
            "created_at": datetime.now().isoformat(),
            **(metadata or {})
        }
        return True
    
    def search(
        self,
        query: str,
        profile_id: Optional[str] = None,
        limit: int = 5,
        score_threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        query_words = set(query.lower().split())
        results = []
        
        for mem in self.memories.values():
            if profile_id and mem["profile_id"] != profile_id:
                continue
            
            content_words = set(mem["content"].lower().split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                score = overlap / max(len(query_words), len(content_words))
                if score >= score_threshold:
                    results.append({**mem, "score": score})
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    def delete_memory(self, memory_id: str) -> bool:
        if memory_id in self.memories:
            del self.memories[memory_id]
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "status": "keyword_fallback",
            "points_count": len(self.memories)
        }


# ============================================================================
# Factory
# ============================================================================

def get_memory_store():
    """Get the best available memory store."""
    if QDRANT_AVAILABLE:
        store = VectorMemoryStore()
        if store.initialized:
            return store
    
    return KeywordMemoryStore()


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Testing memory store...")
    
    store = get_memory_store()
    stats = store.get_stats()
    print(f"Store stats: {stats}")
    
    # Add test memory
    success = store.add_memory(
        memory_id="test-123",
        profile_id="josh",
        content="Josh loves talking about stonks and the giant fish meme",
        memory_type="fact"
    )
    print(f"Add memory: {'✅' if success else '❌'}")
    
    # Search
    results = store.search("stonks", profile_id="josh")
    print(f"Search results: {len(results)}")
    for r in results:
        print(f"  - {r['content'][:50]}... (score: {r['score']:.2f})")
