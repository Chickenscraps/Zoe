import os
import uuid
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

load_dotenv()
load_dotenv(".env.secrets")

EMBEDDING_MODEL = "models/text-embedding-004"

class SupabaseMemoryStore:
    def __init__(self, auto_create_user: bool = False):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        self.client: Optional[Client] = None
        self.initialized = False
        self.auto_create_user = auto_create_user

        if not self.url or not self.key:
            print("⚠️ Supabase Memory Store: missing credentials")
            return
            
        if GENAI_AVAILABLE and self.api_key:
            genai.configure(api_key=self.api_key)
        else:
            print("⚠️ Gemini API Key missing or lib not installed. Embeddings disabled.")

        try:
            self.client = create_client(self.url, self.key)
            self.initialized = True
            print("✅ Supabase Memory Store initialized")
        except Exception as e:
            print(f"⚠️ Supabase init failed: {e}")

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        if not GENAI_AVAILABLE or not self.api_key:
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

    def _get_user_uuid(self, discord_id: str, create_if_missing: bool = False) -> Optional[str]:
        if not self.initialized:
            return None
        try:
            res = self.client.table("users").select("id").eq("discord_id", str(discord_id)).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]["id"]
            if create_if_missing or self.auto_create_user:
                new_user = {"discord_id": str(discord_id), "username": f"User_{str(discord_id)[-4:]}"}
                ins = self.client.table("users").insert(new_user).execute()
                if ins.data and len(ins.data) > 0:
                    return ins.data[0]["id"]
            return None
        except Exception as e:
            # print(f"❌ User lookup/create failed: {e}") 
            # Silent fail for lookup to avoid log spam
            try:
                res = self.client.table("users").select("id").eq("discord_id", str(discord_id)).limit(1).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]["id"]
            except:
                pass
            return None

    def add_memory(self, memory_id: Optional[str], profile_id: str, content: str, memory_type: str, metadata: Dict[str, Any] = None, embedding: Optional[List[float]] = None) -> bool:
        if not self.initialized:
            return False

        user_uuid = self._get_user_uuid(profile_id, create_if_missing=False)
        if not user_uuid:
            # print(f"⚠️ Cannot add memory: user {profile_id} not found.")
            return False

        vector = embedding or self._get_embedding(content)
        if vector is None:
            return False

        payload = {
            "id": memory_id or str(uuid.uuid4()),
            "user_id": user_uuid,
            "content": content,
            "embedding": vector,
            "metadata": { "type": memory_type, "profile_id": profile_id, **(metadata or {}) }
        }

        try:
            self.client.table("memories").insert(payload).execute()
            return True
        except Exception as e:
            print(f"❌ Add Memory Failed: {e}")
            return False

    def search(self, query: str = None, query_embedding: Optional[List[float]] = None, profile_id: Optional[str] = None, limit: int = 5, match_threshold: float = 0.6) -> List[Dict[str, Any]]:
        if not self.initialized:
            return []

        emb = query_embedding or (self._get_embedding(query) if query else None)
        if not emb:
            return []

        filter_user = None
        if profile_id:
            filter_user = self._get_user_uuid(profile_id, create_if_missing=False)

        try:
            params = {
                "query_embedding": emb,
                "match_threshold": float(match_threshold),
                "match_count": int(limit),
                "filter_user_id": filter_user
            }
            res = self.client.rpc("match_memories", params).execute()
            out = []
            if res and getattr(res, "data", None):
                for r in res.data:
                    out.append({
                        "memory_id": r.get("id"),
                        "content": r.get("content"),
                        "score": r.get("similarity") or r.get("score"),
                        "metadata": r.get("metadata")
                    })
            return out
        except Exception as e:
            print(f"❌ Memory Search Failed: {e}")
            return []

    def add_artifact(self, artifact_id: str, instance_id: str, kind: str, related_id: str, url: str, metadata: Dict[str, Any] = None) -> bool:
        """Add artifact metadata record."""
        if not self.initialized:
            return False
        
        payload = {
            "id": artifact_id or str(uuid.uuid4()),
            "instance_id": instance_id,
            "kind": kind,
            "related_id": related_id,
            "url": url,
            "captured_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        try:
            self.client.table("artifacts").insert(payload).execute()
            return True
        except Exception as e:
            print(f"❌ Add Artifact Failed: {e}")
            return False

    def delete_memory(self, memory_id: str) -> bool:
        if not self.initialized:
            return False
        try:
            self.client.table("memories").delete().eq("id", memory_id).execute()
            return True
        except Exception as e:
            print(f"❌ Delete Memory Failed: {e}")
            return False

supabase_memory = SupabaseMemoryStore()
