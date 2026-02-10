"""
Showcase Manager for Clawdbot
Manages showcase candidates with polish checklist gating.
"""
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
import threading

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

SHOWCASE_QUEUE_FILE = os.path.join(SKILL_DIR, "showcase_queue.json")
SHOWCASE_LOG_FILE = os.path.join(SKILL_DIR, "showcase_history.jsonl")


@dataclass
class ShowcaseCandidate:
    """A candidate for showcase."""
    id: str
    created_at: str
    status: str  # pending, ready, sent, rejected
    
    # Required checklist items
    what_is_it: str = ""              # 1-2 sentences
    why_it_matters: str = ""           # Value proposition
    demo_steps: List[str] = field(default_factory=list)  # Reproducible steps
    artifacts: List[str] = field(default_factory=list)   # Screenshots/clips/links/diffs
    self_test_passed: bool = False     # Health check / dry run
    risks_and_rollback: str = ""       # What could go wrong
    audience_fit: str = ""             # Why it's cool for the group
    
    # Metadata
    source: str = ""                   # What triggered this
    correlation_id: str = ""
    checklist_score: int = 0           # How many items pass
    rejection_reason: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'ShowcaseCandidate':
        return cls(**d)


@dataclass
class ChecklistResult:
    """Result of checklist validation."""
    passed: bool
    score: int
    max_score: int
    failures: List[str]
    
    def __str__(self):
        if self.passed:
            return f"✅ Checklist passed ({self.score}/{self.max_score})"
        return f"❌ Checklist failed ({self.score}/{self.max_score}): {', '.join(self.failures)}"


class ShowcaseManager:
    """
    Manages showcase candidates with strict polish gating.
    
    Polish checklist:
    1. What is it? (1-2 sentences)
    2. Why it matters? (value)
    3. Demo steps (reproducible)
    4. Artifacts (screenshot/clip/link/diff)
    5. Basic self-test passed
    6. Risks + rollback steps
    7. Audience fit (why it's cool)
    """
    
    def __init__(self):
        self.settings = self._load_settings()
        self.queue: List[ShowcaseCandidate] = self._load_queue()
        self._lock = threading.Lock()
    
    def _load_settings(self) -> Dict:
        """Load showcase settings."""
        try:
            with open(os.path.join(SKILL_DIR, "settings.json"), "r") as f:
                settings = json.load(f)
                return settings.get("showcase", {
                    "enabled": True,
                    "auto_ping": False,
                    "require_artifacts": True,
                    "require_self_test": True,
                    "min_checklist_items": 5
                })
        except FileNotFoundError:
            return {"enabled": True, "min_checklist_items": 5}
    
    def _load_queue(self) -> List[ShowcaseCandidate]:
        """Load pending showcases from queue."""
        try:
            with open(SHOWCASE_QUEUE_FILE, "r") as f:
                data = json.load(f)
                return [ShowcaseCandidate.from_dict(c) for c in data.get("pending", [])]
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_queue(self):
        """Save pending showcases to queue."""
        with open(SHOWCASE_QUEUE_FILE, "w") as f:
            json.dump({
                "pending": [c.to_dict() for c in self.queue],
                "last_updated": datetime.now().isoformat()
            }, f, indent=2)
    
    def _log_showcase(self, candidate: ShowcaseCandidate, event: str):
        """Log showcase event."""
        with open(SHOWCASE_LOG_FILE, "a") as f:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "event": event,
                "showcase_id": candidate.id,
                "status": candidate.status,
                "checklist_score": candidate.checklist_score
            }
            f.write(json.dumps(entry) + "\n")
    
    def _generate_id(self) -> str:
        """Generate unique showcase ID."""
        import uuid
        return f"showcase_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    def validate_checklist(self, candidate: ShowcaseCandidate) -> ChecklistResult:
        """
        Validate the showcase checklist.
        
        Returns ChecklistResult with pass/fail and details.
        """
        failures = []
        score = 0
        max_score = 7
        
        # 1. What is it?
        if candidate.what_is_it and len(candidate.what_is_it) >= 10:
            score += 1
        else:
            failures.append("Missing 'what_is_it' description")
        
        # 2. Why it matters?
        if candidate.why_it_matters and len(candidate.why_it_matters) >= 10:
            score += 1
        else:
            failures.append("Missing 'why_it_matters' value proposition")
        
        # 3. Demo steps
        if candidate.demo_steps and len(candidate.demo_steps) >= 1:
            score += 1
        else:
            failures.append("Missing demo steps")
        
        # 4. Artifacts (if required)
        if self.settings.get("require_artifacts", True):
            if candidate.artifacts and len(candidate.artifacts) >= 1:
                score += 1
            else:
                failures.append("Missing artifacts (screenshot/clip/link)")
        else:
            score += 1  # Not required, give point
        
        # 5. Self-test passed (if required)
        if self.settings.get("require_self_test", True):
            if candidate.self_test_passed:
                score += 1
            else:
                failures.append("Self-test not passed")
        else:
            score += 1  # Not required, give point
        
        # 6. Risks + rollback
        if candidate.risks_and_rollback and len(candidate.risks_and_rollback) >= 5:
            score += 1
        else:
            failures.append("Missing risks/rollback info")
        
        # 7. Audience fit
        if candidate.audience_fit and len(candidate.audience_fit) >= 5:
            score += 1
        else:
            failures.append("Missing audience fit explanation")
        
        # Calculate pass/fail
        min_required = self.settings.get("min_checklist_items", 5)
        passed = score >= min_required and len(failures) <= 2
        
        return ChecklistResult(
            passed=passed,
            score=score,
            max_score=max_score,
            failures=failures
        )
    
    def submit_candidate(
        self,
        what_is_it: str,
        why_it_matters: str,
        demo_steps: List[str] = None,
        artifacts: List[str] = None,
        self_test_passed: bool = False,
        risks_and_rollback: str = "",
        audience_fit: str = "",
        source: str = "",
        correlation_id: str = ""
    ) -> Tuple[ShowcaseCandidate, ChecklistResult]:
        """
        Submit a new showcase candidate.
        
        Returns:
            (candidate, checklist_result)
        """
        candidate = ShowcaseCandidate(
            id=self._generate_id(),
            created_at=datetime.now().isoformat(),
            status="pending",
            what_is_it=what_is_it,
            why_it_matters=why_it_matters,
            demo_steps=demo_steps or [],
            artifacts=artifacts or [],
            self_test_passed=self_test_passed,
            risks_and_rollback=risks_and_rollback,
            audience_fit=audience_fit,
            source=source,
            correlation_id=correlation_id
        )
        
        # Validate
        result = self.validate_checklist(candidate)
        candidate.checklist_score = result.score
        
        if result.passed:
            candidate.status = "ready"
            self._emit_ready_event(candidate)
        else:
            candidate.rejection_reason = "; ".join(result.failures[:2])
        
        with self._lock:
            self.queue.append(candidate)
            self._save_queue()
        
        self._log_showcase(candidate, "submitted")
        
        return candidate, result
    
    def _emit_ready_event(self, candidate: ShowcaseCandidate):
        """Emit showcase.ready event to event bus."""
        try:
            from event_bus import event_bus, Event
            
            event_bus.publish(Event(
                event_type="showcase.ready",
                payload={
                    "id": candidate.id,
                    "what": candidate.what_is_it,
                    "why": candidate.why_it_matters,
                    "artifacts": candidate.artifacts,
                    "score": candidate.checklist_score
                },
                source="showcase_manager"
            ))
        except ImportError:
            pass
    
    def send_showcase(
        self,
        candidate_id: str,
        allow_everyone: bool = False
    ) -> Tuple[bool, str]:
        """
        Send a ready showcase to Discord.
        
        Args:
            candidate_id: ID of the showcase to send
            allow_everyone: Whether to @everyone (subject to gating)
        
        Returns:
            (success, message)
        """
        # Find candidate
        candidate = None
        for c in self.queue:
            if c.id == candidate_id:
                candidate = c
                break
        
        if not candidate:
            return False, f"Showcase {candidate_id} not found"
        
        if candidate.status != "ready":
            return False, f"Showcase is not ready (status: {candidate.status})"
        
        # Format message
        message = self.format_discord_message(candidate)
        
        # Send to Discord
        try:
            from discord_bridge import discord_bridge
            
            success = discord_bridge.send_showcase(
                message,
                artifacts=candidate.artifacts,
                allow_everyone=allow_everyone
            )
            
            if success:
                candidate.status = "sent"
                self._save_queue()
                self._log_showcase(candidate, "sent")
                return True, f"Showcase {candidate_id} sent successfully"
            else:
                return False, "Discord send failed"
                
        except ImportError:
            return False, "discord_bridge not available"
    
    def format_discord_message(self, candidate: ShowcaseCandidate) -> str:
        """Format showcase for Discord posting."""
        lines = [
            f"**{candidate.what_is_it}**",
            "",
            f"💡 *{candidate.why_it_matters}*",
            ""
        ]
        
        if candidate.demo_steps:
            lines.append("**How to try it:**")
            for i, step in enumerate(candidate.demo_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")
        
        if candidate.risks_and_rollback:
            lines.append(f"⚠️ {candidate.risks_and_rollback}")
        
        return "\n".join(lines)
    
    def get_pending(self) -> List[ShowcaseCandidate]:
        """Get pending showcases."""
        return [c for c in self.queue if c.status == "pending"]
    
    def get_ready(self) -> List[ShowcaseCandidate]:
        """Get ready showcases."""
        return [c for c in self.queue if c.status == "ready"]
    
    def get_status(self) -> Dict:
        """Get showcase manager status."""
        return {
            "enabled": self.settings.get("enabled", True),
            "pending_count": len(self.get_pending()),
            "ready_count": len(self.get_ready()),
            "auto_ping": self.settings.get("auto_ping", False),
            "min_checklist_items": self.settings.get("min_checklist_items", 5)
        }


# Global instance
showcase_manager = ShowcaseManager()


# Convenience functions
def submit_candidate(**kwargs) -> Tuple[ShowcaseCandidate, ChecklistResult]:
    """Submit a showcase candidate."""
    return showcase_manager.submit_candidate(**kwargs)


def send_showcase(candidate_id: str, ping: bool = False) -> Tuple[bool, str]:
    """Send a ready showcase."""
    return showcase_manager.send_showcase(candidate_id, ping)


def get_ready_showcases() -> List[ShowcaseCandidate]:
    """Get showcases ready to send."""
    return showcase_manager.get_ready()


if __name__ == "__main__":
    print("Testing Showcase Manager...")
    
    # Test incomplete submission
    print("\n--- Testing incomplete submission ---")
    candidate, result = submit_candidate(
        what_is_it="New feature",
        why_it_matters=""  # Missing!
    )
    print(result)
    print(f"Status: {candidate.status}")
    
    # Test complete submission
    print("\n--- Testing complete submission ---")
    candidate2, result2 = submit_candidate(
        what_is_it="Mood Engine v2 - Internal moods with masking",
        why_it_matters="Makes the agent feel more alive and human-like",
        demo_steps=[
            "Run: python mood_engine.py",
            "Check current mood: mood_engine.get_current_mood()",
            "Wait 3+ hours or force transition"
        ],
        artifacts=["screenshot: mood_state.json", "diff: mood_engine.py changes"],
        self_test_passed=True,
        risks_and_rollback="Low risk - JSON-based state. Rollback: delete mood_state.json",
        audience_fit="Shows personality depth - team will appreciate the nuance",
        source="test"
    )
    print(result2)
    print(f"Status: {candidate2.status}")
    
    # Check status
    print(f"\nManager status: {json.dumps(showcase_manager.get_status(), indent=2)}")
