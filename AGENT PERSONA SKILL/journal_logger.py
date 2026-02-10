
import json
import time
import os
from datetime import datetime

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
