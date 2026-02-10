
import json
import time
import os
from datetime import datetime
import sys

# Ensure we can import from the AGENT PERSONA SKILL directory
# Current file is in .agent/skills/clawdbot_persona_extended/
# We need to go up 3 levels to root, then into AGENT PERSONA SKILL
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(os.path.join(root_dir, "AGENT PERSONA SKILL"))

try:
    from memory_store import memory
except ImportError:
    print("Warning: detailed memory store not available.")
    memory = None

# Default configuration
DEFAULT_MODE = "organize"
LOG_DIR = os.path.dirname(os.path.abspath(__file__))

def get_log_file(mode):
    return os.path.join(LOG_DIR, f"journal_{mode}.jsonl")

def log_event(event_type, content, metadata=None, mode=DEFAULT_MODE):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "mode": mode,
        "event": event_type,
        "content": content,
        "metadata": metadata or {}
    }
    
    log_file = get_log_file(mode)
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"Error writing to log {log_file}: {e}")

    # Integration with Memory Store (SQLite)
    if memory:
        try:
            if event_type in ["ACTIVITY", "FOCUS", "WORK", "SYSTEM"]:
                # Default duration to 0 if not specified
                duration = metadata.get("duration_minutes", 0) if metadata else 0
                memory.log_activity(event_type, duration, metadata)
                
            elif event_type == "INSIGHT":
                # For insights, we expect key/value in metadata
                if metadata and "key" in metadata and "value" in metadata:
                    memory.set_profile_attr(metadata["key"], metadata["value"])
                    
        except Exception as e:
            print(f"Error writing to memory store: {e}")

def main():
    print("📔 Journal Logger Active (Mode Isolated).")
    log_event("SYSTEM", "Clawdbot Journal Logger Initialized", mode="organize")
    log_event("SYSTEM", "Clawdbot Journal Logger Initialized", mode="trade")
    
    while True:
        # Heartbeat / Mood Check (simulated)
        time.sleep(3600) # Every hour
        # Log to both for heartbeat consistency if needed, or just default
        log_event("HEARTBEAT", "Skill active. Monitoring user context.", mode="organize")

if __name__ == "__main__":
    main()
