
import os
import sys
import json
import asyncio
import sqlite3
from datetime import datetime

# Setup paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from database import init_db, MoodRepository, MemoryRepository, MoodLog, MemoryItem, get_db
from clawdbot import BotConfig, build_system_prompt, USER_MAP

def test_config_persistence():
    print("\n🧪 Testing BotConfig Persistence...")
    config_path = os.path.join(PROJECT_ROOT, "bot_config.json")
    if os.path.exists(config_path):
        os.remove(config_path)
    
    # configs are loaded on init
    config = BotConfig()
    assert config.tones["romance"] == False
    
    # Change and save
    config.tones["romance"] = True
    config.save()
    
    # Reload
    config2 = BotConfig()
    assert config2.tones["romance"] == True
    print("✅ Config persistence works.")

def test_system_prompt_reactivity():
    print("\n🧪 Testing System Prompt Reactivity...")
    # Load config and set tone
    config = BotConfig()
    config.tones["flirt"] = True
    config.save()
    
    # Force reload of module-level config if needed (but here we just rely on the global instance shared state if we were importing it, 
    # but since we import build_system_prompt, we need to make sure it uses the global `bot_config` from clawdbot.py.
    # checking clawdbot.py... it uses the global `bot_config` instance.
    
    # We need to make sure the `bot_config` in `clawdbot` module is the same one we are manipulating, or at least reading from same file.
    # Actually, `clawdbot.py` initializes `bot_config` on module load. 
    # So we need to modify THAT instance.
    import clawdbot
    clawdbot.bot_config.tones["flirt"] = True
    
    prompt = build_system_prompt(None, {}, [])
    
    if "Flirt mode active" in prompt:
        print("✅ System prompt includes 'Flirt mode active'")
    else:
        print("❌ System prompt MISSING 'Flirt mode active'")
        print("Prompt snippet:", prompt[0:500])

def test_privacy_deletion():
    print("\n🧪 Testing Privacy Deletion...")
    init_db()
    
    profile_id = "test_user"
    
    # Insert dummy data
    mood = MoodLog(
        id="test_mood", profile_id=profile_id, timestamp=datetime.now().isoformat(),
        source="text", signals={}
    )
    MoodRepository.insert(mood)
    
    memory = MemoryItem(
        id="test_mem", profile_id=profile_id, type="fact", durability="durable",
        content="foo", confidence=1.0, evidence_refs=[], created_at="now", last_accessed="now"
    )
    MemoryRepository.insert(memory)
    
    # Verify insertion
    with get_db() as conn:
        m_count = conn.execute("SELECT COUNT(*) FROM mood_logs WHERE profile_id=?", (profile_id,)).fetchone()[0]
        mem_count = conn.execute("SELECT COUNT(*) FROM memory_items WHERE profile_id=?", (profile_id,)).fetchone()[0]
    
    print(f"   Inserted {m_count} moods, {mem_count} memories.")
    assert m_count > 0
    assert mem_count > 0
    
    # Delete
    MoodRepository.delete_all(profile_id)
    MemoryRepository.delete_all(profile_id)
    
    # Verify deletion
    with get_db() as conn:
        m_count_post = conn.execute("SELECT COUNT(*) FROM mood_logs WHERE profile_id=?", (profile_id,)).fetchone()[0]
        mem_count_post = conn.execute("SELECT COUNT(*) FROM memory_items WHERE profile_id=?", (profile_id,)).fetchone()[0]
    
    assert m_count_post == 0
    assert mem_count_post == 0
    print("✅ Privacy deletion worked. Data is gone.")

if __name__ == "__main__":
    test_config_persistence()
    test_system_prompt_reactivity()
    test_privacy_deletion()
