"""
Explainability Module for Clawdbot
Tracks decision rationale and provides /explain endpoint data.
"""
import os
import json
from datetime import datetime
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict
import threading

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DECISIONS_LOG = os.path.join(SKILL_DIR, "decisions.jsonl")

@dataclass
class Decision:
    """Records a decision made by the agent."""
    timestamp: str
    correlation_id: str
    action: str
    rationale: str  # Why this decision was made
    inputs_used: List[str]  # What inputs influenced the decision
    outcome: Optional[str] = None  # What happened after
    next_action: Optional[str] = None  # What will happen next
    confidence: float = 1.0  # How confident (0.0-1.0)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())

class ExplainabilityTracker:
    """
    Tracks decisions and provides explanations.
    Stores rationale per correlation_id for later retrieval.
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
    
    def __init__(self):
        if self._initialized:
            return
        
        self._decisions: Dict[str, Decision] = {}  # correlation_id -> Decision
        self._recent: List[Decision] = []
        self._max_recent = 50
        self._file_lock = threading.Lock()
        self._initialized = True
    
    def record_decision(
        self,
        correlation_id: str,
        action: str,
        rationale: str,
        inputs_used: List[str],
        next_action: str = None,
        confidence: float = 1.0
    ) -> Decision:
        """
        Record a decision made by the agent.
        
        Args:
            correlation_id: Links to logs/events
            action: What action was taken
            rationale: Why this decision was made
            inputs_used: What inputs influenced the decision
            next_action: What will happen next
            confidence: Confidence level (0.0-1.0)
        """
        decision = Decision(
            timestamp=datetime.now().isoformat(),
            correlation_id=correlation_id,
            action=action,
            rationale=rationale,
            inputs_used=inputs_used,
            next_action=next_action,
            confidence=confidence
        )
        
        # Store in memory
        self._decisions[correlation_id] = decision
        self._recent.append(decision)
        if len(self._recent) > self._max_recent:
            self._recent = self._recent[-self._max_recent:]
        
        # Persist to log
        self._write_decision(decision)
        
        return decision
    
    def update_outcome(self, correlation_id: str, outcome: str):
        """Update the outcome of a recorded decision."""
        if correlation_id in self._decisions:
            self._decisions[correlation_id].outcome = outcome
            self._write_decision(self._decisions[correlation_id])
    
    def _write_decision(self, decision: Decision):
        """Write decision to log file."""
        with self._file_lock:
            try:
                with open(DECISIONS_LOG, "a", encoding="utf-8") as f:
                    f.write(decision.to_json() + "\n")
            except Exception as e:
                print(f"[Explainability] Write error: {e}")
    
    def get_explanation(self, correlation_id: str) -> Optional[Dict]:
        """Get explanation for a specific correlation_id."""
        if correlation_id in self._decisions:
            return self._decisions[correlation_id].to_dict()
        
        # Try to find in log file
        try:
            with open(DECISIONS_LOG, "r", encoding="utf-8") as f:
                for line in reversed(f.readlines()):
                    try:
                        entry = json.loads(line)
                        if entry.get("correlation_id") == correlation_id:
                            return entry
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        
        return None
    
    def get_last_explanation(self) -> Dict:
        """Get the most recent decision explanation."""
        if self._recent:
            last = self._recent[-1]
            return {
                "correlation_id": last.correlation_id,
                "action": last.action,
                "rationale": last.rationale,
                "inputs_used": last.inputs_used,
                "next_action": last.next_action,
                "outcome": last.outcome,
                "confidence": last.confidence,
                "timestamp": last.timestamp
            }
        
        # Try log file
        try:
            with open(DECISIONS_LOG, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    return json.loads(lines[-1])
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
        return {
            "rationale": "No documented decisions found in recent history.",
            "action": None,
            "inputs_used": []
        }
    
    def get_recent_decisions(self, count: int = 10) -> List[Dict]:
        """Get recent decisions."""
        return [d.to_dict() for d in self._recent[-count:]]
    
    def explain_action(
        self,
        action: str,
        context: Dict,
        correlation_id: str = None
    ) -> str:
        """
        Generate a human-readable explanation for an action.
        Used for user-facing explanations.
        """
        # Templates for common actions
        templates = {
            "sweep_desktop": "Your desktop has {file_count} files, which is above the clutter threshold. I suggested cleaning to help you focus.",
            "calendar_check": "I proactively checked your calendar because {reason}.",
            "mood_change": "My mood shifted from {old_mood} to {new_mood} as part of my natural personality variation.",
            "news_post": "I shared headlines because {reason}. The news seems {sentiment} overall.",
            "nudge": "I reached out because it's been {idle_time} since your last activity.",
            "vision_check": "I looked at your screen to {purpose}.",
            "default": "I took this action based on: {inputs}"
        }
        
        template = templates.get(action, templates["default"])
        
        try:
            explanation = template.format(**context)
        except KeyError:
            explanation = f"Action: {action}. Context: {context}"
        
        # Record the decision
        if correlation_id:
            import uuid
            cid = correlation_id or str(uuid.uuid4())
            self.record_decision(
                correlation_id=cid,
                action=action,
                rationale=explanation,
                inputs_used=list(context.keys())
            )
        
        return explanation

# Global singleton instance
explainability = ExplainabilityTracker()

# Convenience functions
def record_decision(
    correlation_id: str,
    action: str,
    rationale: str,
    inputs_used: List[str] = None,
    **kwargs
) -> Decision:
    """Record a decision."""
    return explainability.record_decision(
        correlation_id=correlation_id,
        action=action,
        rationale=rationale,
        inputs_used=inputs_used or [],
        **kwargs
    )

def explain_last() -> Dict:
    """Get the last decision explanation."""
    return explainability.get_last_explanation()

def explain_action(action: str, context: Dict, correlation_id: str = None) -> str:
    """Generate explanation for an action."""
    return explainability.explain_action(action, context, correlation_id)

if __name__ == "__main__":
    import uuid
    
    # Test
    print("Testing Explainability Tracker...")
    
    cid = str(uuid.uuid4())
    
    decision = record_decision(
        correlation_id=cid,
        action="sweep_desktop",
        rationale="User has 25 files on desktop, exceeding clutter threshold",
        inputs_used=["desktop_file_count", "clutter_threshold"],
        next_action="await_user_confirmation"
    )
    
    print(f"\nRecorded: {decision.action}")
    
    last = explain_last()
    print(f"\nLast decision:")
    print(f"  Action: {last['action']}")
    print(f"  Rationale: {last['rationale']}")
    print(f"  Inputs: {last['inputs_used']}")
    
    explanation = explain_action(
        "sweep_desktop",
        {"file_count": 25},
        cid
    )
    print(f"\nExplanation: {explanation}")
