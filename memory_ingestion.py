"""
Memory Ingestion Pipeline for Clawdbot
Extracts memories and facts from chat history using Gemini 2.0
"""
import os
import json
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# import ollama (Removed)

from database import (
    ProfileRepository, MemoryRepository, MoodRepository,
    UserProfile, MemoryItem, MessageRepository
)
from vector_store import get_memory_store

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
PERSONA_SKILL_DIR = PROJECT_ROOT / "AGENT PERSONA SKILL"

# Message files
MESSAGE_FILES = {
    "josh": PERSONA_SKILL_DIR / "josh_messages.json",
    "ben": PERSONA_SKILL_DIR / "ben_messages.json",
    "zac": PERSONA_SKILL_DIR / "zac_messages.json",
}

# Memory extraction settings
CHUNK_SIZE = 20  # Messages per chunk for extraction
MAX_CHUNKS_PER_RUN = 50  # Limit per run to avoid overwhelming

# ============================================================================
# Chunking
# ============================================================================

def load_messages(profile_id: str, limit: Optional[int] = None, since_year: Optional[int] = None) -> List[Dict]:
    """Load messages for a profile, optionally filtered by year."""
    file_path = MESSAGE_FILES.get(profile_id)
    if not file_path or not file_path.exists():
        print(f"⚠️ No message file for {profile_id}")
        return []
    
    with open(file_path, "r", encoding="utf-8") as f:
        messages = json.load(f)
    
    if since_year:
        cutoff = datetime(since_year, 1, 1).isoformat()
        messages = [m for m in messages if m.get("timestamp", "") >= cutoff]
        print(f"   Filtered to {len(messages)} messages since {since_year}")

    if limit:
        messages = messages[:limit]
    
    return messages


def chunk_messages(messages: List[Dict], chunk_size: int = CHUNK_SIZE) -> List[List[Dict]]:
    """Split messages into chunks for processing."""
    return [messages[i:i + chunk_size] for i in range(0, len(messages), chunk_size)]


# ============================================================================
# Memory Extraction
# ============================================================================

EXTRACTION_PROMPT = """You are the Memory Manager for Zoe.
Your goal is to extract **PERMANENT, SIGNIFICANT FACTS** about the user "{profile_id}".

❌ DO NOT EXTRACT:
- Temporary moods ("User is happy today")
- Trivial chatter ("User said hi", "User is testing the bot")
- Communication style observations (e.g. "User uses lowercase") - We already know this.
- Speculation or guesses.

✅ DO EXTRACT (Only if clear):
- **Specific Permissions/Rules**: "User said Ben is NOT allowed to use admin tools."
- **Hard Preferences**: "User loves Rush but hates Metallica."
- **Biographical Info**: "User lives in Seattle", "User works at Google."
- **Project/Work Context**: "User is working on the 'Zoe V3' update."

Return JSON array of facts. If nothing significant is found, return [].

Example Output:
[
  {{"type": "preference", "content": "{profile_id} prefers 'dark mode' for UI design", "confidence": 0.9}},
  {{"type": "biography", "content": "{profile_id} has a cat named Luna", "confidence": 0.95}}
]

MESSAGES FROM {profile_id}:
{messages}

Extract ONLY significant, durable facts (or []):"""


async def extract_memories_from_chunk(
    profile_id: str,
    messages: List[Dict]
) -> List[Dict]:
    """Extract memories from a message chunk using Llama."""
    # Format messages for prompt
    formatted_messages = []
    for msg in messages:
        content = msg.get("content", msg.get("text", ""))
        timestamp = msg.get("timestamp", "")
        formatted_messages.append(f"[{timestamp}] {content}")
    
    messages_text = "\n".join(formatted_messages[-CHUNK_SIZE:])
    
    prompt = EXTRACTION_PROMPT.format(
        profile_id=profile_id.capitalize(),
        messages=messages_text
    )
    
    # Gemini Migration (Phase 1)
    # We use model_router if available, or just skip if script run standalone without env
    try:
        # Hacky import to avoid circular dependency if any
        # Assuming model_router is in path
        from model_router import model_router
        
        # Construct message list for router
        messages = [{"role": "user", "content": prompt}]
        
        # Call Gemini
        # default to flash-lite
        response_text = await model_router.chat(
            messages=messages,
            model="gemini-2.0-flash-lite",
            system="You are an expert analyst of chat history."
        )
        
        content = response_text
        
        # Parse JSON
        try:
            facts = json.loads(content)
            if isinstance(facts, list):
                return facts
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        
        return []
    except Exception as e:
        print(f"⚠️ Extraction failed: {e}")
        return []


# ============================================================================
# Memory Storage
# ============================================================================

def store_memory(profile_id: str, fact: Dict) -> bool:
    """Store a memory in both SQLite and vector store."""
    memory_id = str(uuid.uuid4())
    content = fact.get("content", "")
    memory_type = fact.get("type", "fact")
    confidence = fact.get("confidence", 0.7)
    
    # Store in SQLite
    memory = MemoryItem(
        id=memory_id,
        profile_id=profile_id,
        type=memory_type,
        durability="durable",
        content=content,
        confidence=confidence,
        evidence_refs=[],
        created_at=datetime.now().isoformat(),
        last_accessed=datetime.now().isoformat(),
        access_count=0
    )
    
    MemoryRepository.insert(memory)
    
    # Store in vector store
    store = get_memory_store()
    store.add_memory(
        memory_id=memory_id,
        profile_id=profile_id,
        content=content,
        memory_type=memory_type,
        metadata={"confidence": confidence}
    )
    
    return True


# ============================================================================
# Pipeline
# ============================================================================

async def run_ingestion(
    profile_id: str,
    max_chunks: int = MAX_CHUNKS_PER_RUN,
    skip_chunks: int = 0,
    since_year: Optional[int] = None
) -> Dict[str, Any]:
    """Run memory ingestion for a profile."""
    print(f"\n🧠 Starting ingestion for {profile_id}...")
    
    # Load messages
    messages = load_messages(profile_id, since_year=since_year)
    if not messages:
        return {"status": "error", "reason": "no_messages"}
    
    print(f"   Loaded {len(messages)} messages")
    
    # Chunk messages
    chunks = chunk_messages(messages)
    chunks = chunks[skip_chunks:skip_chunks + max_chunks]
    print(f"   Processing {len(chunks)} chunks (skipped {skip_chunks})")
    
    # Process chunks
    total_facts = 0
    for i, chunk in enumerate(chunks):
        print(f"   Processing chunk {i + 1}/{len(chunks)}...", end=" ")
        
        facts = await extract_memories_from_chunk(profile_id, chunk)
        
        # Store each fact
        for fact in facts:
            store_memory(profile_id, fact)
            total_facts += 1
        
        print(f"extracted {len(facts)} facts")
        
        # Small delay to avoid overwhelming API
        await asyncio.sleep(0.5)
    
    print(f"\n✅ Ingestion complete: {total_facts} facts extracted")
    
    return {
        "status": "success",
        "profile_id": profile_id,
        "chunks_processed": len(chunks),
        "facts_extracted": total_facts
    }


async def run_full_ingestion(max_chunks_per_profile: int = 10, since_year: Optional[int] = None):
    """Run ingestion for all profiles."""
    results = {}
    
    for profile_id in MESSAGE_FILES.keys():
        result = await run_ingestion(profile_id, max_chunks=max_chunks_per_profile, since_year=since_year)
        results[profile_id] = result
    
    return results


async def ingest_recent_history(hours: int = 24, max_messages: int = 100) -> Dict[str, Any]:
    """
    Ingest memories from recent message_events (Live Chat).
    This is different from run_ingestion which uses static JSON files.
    """
    print(f"\n🧠 Ingesting recent history (last {hours}h)...")
    
    from datetime import datetime, timedelta
    from database import get_db
    
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    # Fetch recent messages grouped by profile
    with get_db() as conn:
        rows = conn.execute("""
            SELECT profile_id, content, timestamp 
            FROM message_events 
            WHERE timestamp > ? AND profile_id IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT ?
        """, (cutoff, max_messages)).fetchall()
    
    if not rows:
        print("   No new messages to ingest.")
        return {"status": "no_messages"}
    
    print(f"   Found {len(rows)} messages to process")
    
    # Group by profile
    by_profile: Dict[str, List[Dict]] = {}
    for row in rows:
        pid = row["profile_id"]
        if pid not in by_profile:
            by_profile[pid] = []
        by_profile[pid].append({"content": row["content"], "timestamp": row["timestamp"]})
    
    total_facts = 0
    for profile_id, messages in by_profile.items():
        print(f"   Processing {len(messages)} messages for {profile_id}...")
        
        # Chunk if needed
        chunks = chunk_messages(messages, CHUNK_SIZE)
        for chunk in chunks[:3]:  # Limit chunks per run
            facts = await extract_memories_from_chunk(profile_id, chunk)
            for fact in facts:
                store_memory(profile_id, fact)
                total_facts += 1
            await asyncio.sleep(0.2)
    
    print(f"\n✅ Live ingestion complete: {total_facts} facts extracted")
    return {"status": "success", "facts_extracted": total_facts}


# ============================================================================
# Quick Stats
# ============================================================================

def print_stats():
    """Print current memory stats."""
    print("\n📊 Memory Stats:")
    
    for profile_id in ["josh", "ben", "zac"]:
        memories = MemoryRepository.get_by_profile(profile_id, limit=1000)
        print(f"   {profile_id}: {len(memories)} memories")
    
    store = get_memory_store()
    stats = store.get_stats()
    print(f"\n   Vector store: {stats}")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            print_stats()
        elif sys.argv[1] == "ingest":
            profile = sys.argv[2] if len(sys.argv) > 2 else None
            if profile and profile.lower() in ["all", "none", "any"]:
                profile = None
            chunks = int(sys.argv[3]) if len(sys.argv) > 3 else 5
            since = int(sys.argv[4]) if len(sys.argv) > 4 else None
            
            if profile:
                asyncio.run(run_ingestion(profile, max_chunks=chunks, since_year=since))
            else:
                asyncio.run(run_full_ingestion(max_chunks_per_profile=chunks, since_year=since))
            
            print_stats()
    else:
        print("Usage:")
        print("  python memory_ingestion.py stats")
        print("  python memory_ingestion.py ingest [profile] [max_chunks]")
        print("\nExamples:")
        print("  python memory_ingestion.py ingest josh 10")
        print("  python memory_ingestion.py ingest        # All profiles, 10 chunks each")
