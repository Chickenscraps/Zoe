import json
import os
from datetime import datetime
import uuid

LOG_FILE = "clawdbot_journal.jsonl"

def log_event(event_type, content, metadata=None, mode="normal", correlation_id=None, rationale=None):
    """
    Logs an event to a mode-specific journal file with correlation support.
    """
    log_file = f"journal_{mode}.jsonl"
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "content": content,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "rationale": rationale,
        "metadata": metadata or {}
    }
    # Ensure SKILL_DIR context if called from dispatcher
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(skill_dir, log_file)
    
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

def get_log_file(mode):
    return f"journal_{mode}.jsonl"
