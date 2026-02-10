"""
Structured Logger for Clawdbot
JSONL structured logging with correlation IDs and model metadata.
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import threading

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = SKILL_DIR
MAIN_LOG = os.path.join(LOG_DIR, "clawdbot_structured.jsonl")

@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: str
    level: str  # DEBUG, INFO, WARN, ERROR
    event: str  # Event type/name
    message: str
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None
    source: Optional[str] = None
    mode: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        # Remove None values
        return {k: v for k, v in d.items() if v is not None}
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())

@dataclass
class ModelCallLog:
    """Log entry for model/LLM calls."""
    timestamp: str
    model: str
    input_preview: str  # First 200 chars of input
    output_preview: str  # First 200 chars of output
    latency_ms: float
    success: bool
    error: Optional[str] = None
    retries: int = 0
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())

class StructuredLogger:
    """
    Thread-safe structured logger with JSONL output.
    Supports multiple log levels and correlation tracking.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, log_path: str = MAIN_LOG):
        if self._initialized:
            return
        
        self.log_path = log_path
        self._file_lock = threading.Lock()
        self._current_correlation_id: Optional[str] = None
        self._initialized = True
    
    def set_correlation_id(self, correlation_id: str):
        """Set the current correlation ID for subsequent logs."""
        self._current_correlation_id = correlation_id
    
    def clear_correlation_id(self):
        """Clear the current correlation ID."""
        self._current_correlation_id = None
    
    def _write(self, entry: LogEntry):
        """Write a log entry to the file."""
        with self._file_lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(entry.to_json() + "\n")
            except Exception as e:
                print(f"[Logger] Write error: {e}")
    
    def log(
        self,
        level: str,
        event: str,
        message: str,
        correlation_id: str = None,
        request_id: str = None,
        source: str = None,
        mode: str = None,
        metadata: Dict[str, Any] = None
    ):
        """Log a structured event."""
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level.upper(),
            event=event,
            message=message,
            correlation_id=correlation_id or self._current_correlation_id,
            request_id=request_id,
            source=source,
            mode=mode,
            metadata=metadata
        )
        self._write(entry)
        
        # Also print for visibility
        print(f"[{level.upper()}] {event}: {message[:100]}...")
    
    def debug(self, event: str, message: str, **kwargs):
        self.log("DEBUG", event, message, **kwargs)
    
    def info(self, event: str, message: str, **kwargs):
        self.log("INFO", event, message, **kwargs)
    
    def warn(self, event: str, message: str, **kwargs):
        self.log("WARN", event, message, **kwargs)
    
    def error(self, event: str, message: str, **kwargs):
        self.log("ERROR", event, message, **kwargs)
    
    def log_request(self, user_input: str, correlation_id: str, source: str = "user"):
        """Log an incoming user request."""
        self.info(
            "request.incoming",
            f"User request received: {user_input[:100]}...",
            correlation_id=correlation_id,
            source=source,
            metadata={"input": user_input[:500]}
        )
    
    def log_model_call(
        self,
        model: str,
        input_text: str,
        output_text: str,
        latency_ms: float,
        success: bool,
        error: str = None,
        retries: int = 0,
        correlation_id: str = None
    ):
        """Log a model/LLM call with metadata."""
        entry = ModelCallLog(
            timestamp=datetime.now().isoformat(),
            model=model,
            input_preview=input_text[:200] if input_text else "",
            output_preview=output_text[:200] if output_text else "",
            latency_ms=latency_ms,
            success=success,
            error=error,
            retries=retries,
            correlation_id=correlation_id or self._current_correlation_id
        )
        
        with self._file_lock:
            log_path = os.path.join(LOG_DIR, "model_calls.jsonl")
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(entry.to_json() + "\n")
            except Exception as e:
                print(f"[Logger] Model call write error: {e}")
    
    def log_action(
        self,
        action: str,
        status: str,  # proposed, confirmed, executed, cancelled
        rationale: str,
        correlation_id: str = None,
        metadata: Dict[str, Any] = None
    ):
        """Log an action proposed or taken."""
        self.info(
            f"action.{status}",
            f"{action} - {rationale}",
            correlation_id=correlation_id,
            metadata={
                "action": action,
                "status": status,
                "rationale": rationale,
                **(metadata or {})
            }
        )
    
    def log_event_emitted(self, event_type: str, payload: Dict, correlation_id: str = None):
        """Log an event that was emitted to the event bus."""
        self.debug(
            "event.emitted",
            f"Event emitted: {event_type}",
            correlation_id=correlation_id,
            metadata={"event_type": event_type, "payload": payload}
        )
    
    def get_recent_logs(self, count: int = 50, level: str = None) -> list:
        """Get recent log entries."""
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-count * 2:]  # Read more in case of filtering
            
            logs = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    if level is None or entry.get("level") == level.upper():
                        logs.append(entry)
                except json.JSONDecodeError:
                    continue
            
            return logs[-count:]
        except FileNotFoundError:
            return []
    
    def get_logs_by_correlation_id(self, correlation_id: str) -> list:
        """Get all logs for a specific correlation ID."""
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            logs = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get("correlation_id") == correlation_id:
                        logs.append(entry)
                except json.JSONDecodeError:
                    continue
            
            return logs
        except FileNotFoundError:
            return []

# Global singleton instance
logger = StructuredLogger()

# Convenience functions
def log_info(event: str, message: str, **kwargs):
    logger.info(event, message, **kwargs)

def log_error(event: str, message: str, **kwargs):
    logger.error(event, message, **kwargs)

def log_request(user_input: str, correlation_id: str):
    logger.log_request(user_input, correlation_id)

def log_model_call(**kwargs):
    logger.log_model_call(**kwargs)

if __name__ == "__main__":
    import uuid
    
    # Test
    cid = str(uuid.uuid4())
    logger.set_correlation_id(cid)
    
    logger.info("test.start", "Testing structured logger")
    logger.log_request("Hello, how are you?", cid)
    logger.log_model_call(
        model="gemini-2.0-flash",
        input_text="Hello, how are you?",
        output_text="I'm doing great! How can I help?",
        latency_ms=150.5,
        success=True,
        correlation_id=cid
    )
    logger.log_action("sweep_desktop", "proposed", "User has 20+ files on desktop", cid)
    
    print(f"\nRecent logs: {len(logger.get_recent_logs(10))}")
    print(f"Logs for {cid}: {len(logger.get_logs_by_correlation_id(cid))}")
