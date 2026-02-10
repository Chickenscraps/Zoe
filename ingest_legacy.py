import json
import os
import asyncio
from pathlib import Path
from datetime import datetime
import uuid
from vector_store import get_memory_store

# Files to ingest
FILES = [
    "AGENT PERSONA SKILL/josh_messages.json",
    "AGENT PERSONA SKILL/ben_messages.json",
    "AGENT PERSONA SKILL/zac_messages.json"
]

def ingest_file(filepath, store):
    path = Path(filepath)
    if not path.exists():
        print(f"⚠️ File not found: {path}")
        return 0
    
    print(f"Processing {path}...")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Limit to last 2000 messages for speed (MVP)
        data = data[-2000:]
        
        count = 0
        skipped = 0
        
        # Data format: [{"content": "...", "timestamp": "...", "author": "..."}]
        for entry in data:
            content = entry.get("content", "").strip()
            author = entry.get("author", "Unknown")
            # Map author names to IDs if possible, or key by name?
            # Memory store keys by profile_id.
            profile_map = {
                "Josh": "josh",
                "Ben": "ben", 
                "Zac": "zac"
            }
            profile_id = profile_map.get(author, author.lower())
            
            # FILTERS
            # 1. Length: Ignore short messages (< 15 chars) unless specific keywords
            if len(content) < 15:
                skipped += 1
                continue
                
            # 2. Boring stuff
            if content.lower() in ["lol", "lmao", "ok", "yes", "no", "cool", "thanks"]:
                skipped += 1
                continue

            # Add to store
            try:
                msg_id = str(uuid.uuid4())
                result = store.add_memory(
                    memory_id=msg_id,
                    profile_id=profile_id,
                    content=f"[{author}]: {content}", # Contextualize content
                    memory_type="chat_history",
                    metadata={
                        "original_timestamp": entry.get("timestamp"),
                        "source": "legacy_import"
                    }
                )
                if result:
                    count += 1
                    if count % 100 == 0:
                        print(f"  - Ingested {count} messages...", end="\r")
            except Exception as e:
                print(f"  ❌ Error on item: {e}")
                
        print(f"✅ Finished {path}: {count} ingested, {skipped} skipped.")
        return count
        
    except Exception as e:
        print(f"❌ Failed to process {path}: {e}")
        return 0

if __name__ == "__main__":
    print("🚀 Starting Legacy Memory Ingestion...")
    store = get_memory_store()
    stats = store.get_stats()
    print(f"Initial Store Stats: {stats}")
    
    total = 0
    for f in FILES:
        total += ingest_file(f, store)
        
    print(f"\n🎉 Total Messages Ingested: {total}")
