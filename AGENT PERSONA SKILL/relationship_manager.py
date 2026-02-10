import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Import local modules
try:
    from memory_store import memory
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from memory_store import memory

class RelationshipManager:
    """
    Manages relationship context for different users.
    Tracks intimacy, nicknames, and shared history.
    """
    
    def __init__(self):
        self.registry_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_registry.json")
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """Load user registry from JSON."""
        try:
            with open(self.registry_path, "r") as f:
                return json.load(f).get("users", {})
        except FileNotFoundError:
            return {}

    def get_user_metadata(self, user_id: str) -> Dict[str, Any]:
        """Get static metadata from registry."""
        return self.registry.get(user_id, {"name": "Unknown", "role": "guest"})

    def get_relationship_context(self, user_id: str) -> str:
        """
        Build a text context describing the relationship with the user.
        Used for system prompt injection.
        """
        meta = self.get_user_metadata(user_id)
        name = meta.get("name", "User")
        
        # Fetch dynamic state from MemoryStore user_profile
        intimacy = memory.get_profile_attr("intimacy", user_id) or 0
        nickname = memory.get_profile_attr("nickname", user_id)
        history_summary = memory.get_profile_attr("history_summary", user_id)
        
        context = f"User: {name} (ID: {user_id[-4:]})\n"
        context += f"Role: {meta.get('role', 'guest')}\n"
        context += f"Intimacy Level: {intimacy}/100\n"
        
        if nickname:
            context += f"Nickname: {nickname}\n"
            
        if history_summary:
            context += f"History: {history_summary}\n"
            
        return context

    def update_intimacy(self, user_id: str, delta: int):
        """Update intimacy score."""
        current = memory.get_profile_attr("intimacy", user_id) or 0
        new_val = max(0, min(100, current + delta))
        memory.set_profile_attr("intimacy", new_val, user_id)
        return new_val

    def set_history_summary(self, user_id: str, summary: str):
        """Update the shared history summary."""
        memory.set_profile_attr("history_summary", summary, user_id)

    def get_user_name(self, user_id: str) -> str:
        """Get preferred name (nickname or registry name)."""
        nick = memory.get_profile_attr("nickname", user_id)
        if nick: return nick
        return self.get_user_metadata(user_id).get("name", "User")

relationship_manager = RelationshipManager()
