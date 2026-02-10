import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(".env.secrets")

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

try:
    if url and key and "mock" not in key:
        supabase: Client = create_client(url, key)
    else:
        print("⚠️ Supabase: Mock/Missing key. Database features disabled.")
        supabase = None
except Exception as e:
    print(f"⚠️ Supabase Init Failed: {e}")
    supabase = None

def query_database(table: str, query: str = None):
    """
    Query the Supabase database. 
    (Placeholder: In a real scenario, this would parse SQL or natural language to Supabase queries)
    """
    try:
        if not supabase:
            return "Database Error: Client not initialized."
        response = supabase.table(table).select("*").execute()

        return response.data
    except Exception as e:
        return f"Database Error: {e}"

def add_memory(user_id: str, content: str, category: str = "fact"):
    """Log a new memory about a user."""
    try:
        if not supabase:
            return "Error: Database not connected."
        data = {"user_id": user_id, "content": content, "category": category}
        return supabase.table("memories").insert(data).execute()

    except Exception as e:
        return f"Error adding memory: {e}"

def get_memories(user_id: str, limit: int = 5):
    """Retrieve recent memories for a user."""
    try:
        if not supabase:
            return []
        # TODO: Add vector search here later
        return supabase.table("memories").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()

    except Exception as e:
        return []

def get_or_create_user(discord_id: str, username: str):
    """Get user profile or create if new."""
    try:
        if not supabase:
            return {"discord_id": discord_id, "username": username} # Mock return
        # Check if exists
        res = supabase.table("users").select("*").eq("discord_id", discord_id).execute()

        if res.data:
            return res.data[0]
        
        # Create
        data = {"discord_id": discord_id, "username": username}
        res = supabase.table("users").insert(data).execute()
        return res.data[0]
    except Exception as e:
        print(f"User sync error: {e}")
        return None

def log_journal(entry: str, mood: str):
    """Log to Zoe's internal diary."""
    try:
        supabase.table("journal").insert({"entry": entry, "mood": mood}).execute()
    except Exception as e:
        print(f"Journal error: {e}")

def get_constitution():
    """Fetch active rules from the constitution."""
    try:
        res = supabase.table("constitution").select("rule").eq("active", True).execute()
        if res.data:
            return [r['rule'] for r in res.data]
        return []
    except Exception as e:
        print(f"Constitution error: {e}")
        return []

def add_rule(rule: str, reason: str = "Initial Seed"):
    """Add a new rule to the constitution."""
    try:
        data = {"rule": rule, "reason": reason, "active": True}
        return supabase.table("constitution").insert(data).execute()
    except Exception as e:
        return f"Error adding rule: {e}"

def add_theme(content: str, type: str = "social_archetype"):
    """Add a new social archetype/theme."""
    try:
        data = {"content": content, "type": type}
        return supabase.table("themes").insert(data).execute()
    except Exception as e:
        return f"Error adding theme: {e}"

def get_random_theme():
    """Get a random social theme for inspiration."""
    try:
        # Supabase doesn't have a native random() in simple select without RPC
        # So we fetch a few and pick one in python, or use a specific RPC if we had one.
        # Fetching 20 to pick from.
        res = supabase.table("themes").select("content").limit(20).execute()
        if res.data:
            import random
            return random.choice(res.data)['content']
        return "the silence between keystrokes" # Fallback vibe
    except Exception as e:
        print(f"Theme fetch error: {e}")
        return "digital decay"
