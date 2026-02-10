import random
from typing import List
from database_tool import add_theme, get_random_theme, get_memories
from database import MessageRepository
from model_router import model_router

class MemoryEngine:
    def __init__(self):
        self.cached_themes = []

    def get_social_context(self) -> str:
        """
        Retrieve a 'Social Archetype' to inspire the next thought.
        """
        theme = get_random_theme()
        
        # Also fetch a random recent memory to ground it
        recents = get_memories("global_context", limit=1)
        recent_txt = recents[0]['content'] if recents else "we exist in a void"
        
        return f"""
        Selected Archetype: "{theme}"
        Recent Echo: "{recent_txt}"
        
        (Use this archetype to dream a new thread. Do not repeat it directly.)
        """

    async def ingest_recent_history(self, hours: int = 24) -> str:
        """
        Scan recent chat history and extract new 'Social Archetypes'.
        """
        try:
            # 1. Fetch recent messages
            messages = MessageRepository.get_recent("global", limit=50) 
            if not messages:
                return "No messages to analyze."

            text_block = "\n".join([f"{m.user_id}: {m.content}" for m in messages])
            
            # 2. Analyze with LLM
            prompt = f"""
            Analyze the following chat logs (Social Memory Scan).
            Identify 3-5 "Social Archetypes" or "Vibe Clusters".
            
            Rules:
            - Ignore surface topics (e.g. "python", "weather").
            - Look for emotional loops, recurring obsessions, or shared delusions.
            - Format: JSON list of strings.
            - Examples: ["tools that feel like thoughts", "friendly recursion", "paranoid design"]
            
            Logs:
            {text_block[:4000]}
            """
            
            response_text = await model_router.chat(
                messages=[{"role": "user", "content": prompt}]
            )
            
            # 3. Parse and Save
            import re
            matches = re.findall(r'["\'](.*?)["\']', response_text)
            
            added = []
            for theme in matches:
                # Filter noise
                if len(theme) > 5 and len(theme) < 50 and " " in theme:
                    add_theme(theme, type="extracted_archetype")
                    added.append(theme)
            
            return f"Ingested {len(added)} new archetypes: {', '.join(added[:3])}..."
            
        except Exception as e:
            return f"Ingestion failed: {e}"

memory_engine = MemoryEngine()
