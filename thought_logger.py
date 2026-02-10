import os
import json
import threading
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = PROJECT_ROOT / "logs" / "live_transcript.jsonl"

class ThoughtLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ThoughtLogger, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = True

    def log(self, event_type: str, content: str, metadata: dict = None):
        """Log an event to the JSONL file."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "content": content,
            "metadata": metadata or {}
        }
        
        with self._lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

# Global singleton
thought_logger = ThoughtLogger()
