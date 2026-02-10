"""
Affect Engine for Clawdbot
Internal salience scoring for strong-feeling @everyone pings.
Computes conviction, urgency, impact, novelty, alignment, emotional intensity.
"""
import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass, asdict
import threading

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

AFFECT_STATE_FILE = os.path.join(SKILL_DIR, "affect_state.json")
AFFECT_LOG_FILE = os.path.join(SKILL_DIR, "affect_history.jsonl")


@dataclass
class AffectState:
    """
    Internal affect/salience state.
    All values 0.0 to 1.0.
    """
    conviction: float = 0.5      # How confident the agent is
    urgency: float = 0.3         # Time sensitivity
    impact: float = 0.5          # Expected user value / risk avoided
    novelty: float = 0.5         # Is this new/rare
    alignment: float = 0.7       # Aligned with user/team goals
    emotional_intensity: float = 0.3  # Internal arousal
    
    # Metadata
    timestamp: str = ""
    reason: str = ""
    source: str = ""
    
    @property
    def salience_score(self) -> float:
        """
        Compute weighted salience score.
        
        Formula:
        - conviction: 25% (how sure we are)
        - urgency: 20% (time pressure)
        - impact: 20% (value/risk)
        - novelty: 15% (rarity)
        - alignment: 10% (goal match)
        - emotional_intensity: 10% (internal feeling)
        """
        weights = self._get_weights()
        
        score = (
            weights["conviction"] * self.conviction +
            weights["urgency"] * self.urgency +
            weights["impact"] * self.impact +
            weights["novelty"] * self.novelty +
            weights["alignment"] * self.alignment +
            weights["emotional_intensity"] * self.emotional_intensity
        )
        
        return min(1.0, max(0.0, score))
    
    def _get_weights(self) -> Dict[str, float]:
        """Get salience weights from settings."""
        try:
            with open(os.path.join(SKILL_DIR, "settings.json"), "r") as f:
                settings = json.load(f)
                return settings.get("strong_feeling", {}).get("weights", {
                    "conviction": 0.25,
                    "urgency": 0.20,
                    "impact": 0.20,
                    "novelty": 0.15,
                    "alignment": 0.10,
                    "emotional_intensity": 0.10
                })
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "conviction": 0.25,
                "urgency": 0.20,
                "impact": 0.20,
                "novelty": 0.15,
                "alignment": 0.10,
                "emotional_intensity": 0.10
            }
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["salience_score"] = self.salience_score
        return d
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'AffectState':
        # Remove computed fields
        d.pop("salience_score", None)
        return cls(**d)


@dataclass
class SanityGateResult:
    """Result of sanity gate check."""
    passed: bool
    failures: List[str]
    
    def __str__(self):
        if self.passed:
            return "✅ Sanity gate passed"
        return f"❌ Sanity gate failed: {', '.join(self.failures)}"


class AffectEngine:
    """
    Manages internal affect state and strong-feeling ping decisions.
    This is the agent's internal emotional/salience gauge.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    # Salience threshold for @everyone
    DEFAULT_SALIENCE_THRESHOLD = 0.92
    
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
        
        self._current_state = AffectState(timestamp=datetime.now().isoformat())
        self._file_lock = threading.Lock()
        self._load_state()
        self._initialized = True
    
    def _load_settings(self) -> Dict:
        """Load strong_feeling settings."""
        try:
            with open(os.path.join(SKILL_DIR, "settings.json"), "r") as f:
                settings = json.load(f)
                return settings.get("strong_feeling", {
                    "enabled": True,
                    "salience_threshold": self.DEFAULT_SALIENCE_THRESHOLD,
                    "max_pings_per_day": 1,
                    "ask_josh_first": True
                })
        except FileNotFoundError:
            return {"enabled": True, "salience_threshold": self.DEFAULT_SALIENCE_THRESHOLD}
    
    def _load_state(self):
        """Load persisted affect state."""
        try:
            with open(AFFECT_STATE_FILE, "r") as f:
                data = json.load(f)
                self._current_state = AffectState.from_dict(data)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    def _save_state(self):
        """Save current affect state."""
        with self._file_lock:
            with open(AFFECT_STATE_FILE, "w") as f:
                json.dump(self._current_state.to_dict(), f, indent=2)
    
    def _log_affect(self, event_type: str, details: Dict = None):
        """Log affect events for analysis."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "state": self._current_state.to_dict(),
            "details": details or {}
        }
        with open(AFFECT_LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def update(
        self,
        conviction: float = None,
        urgency: float = None,
        impact: float = None,
        novelty: float = None,
        alignment: float = None,
        emotional_intensity: float = None,
        reason: str = "",
        source: str = ""
    ):
        """
        Update affect state components.
        Only provided values are updated.
        """
        if conviction is not None:
            self._current_state.conviction = min(1.0, max(0.0, conviction))
        if urgency is not None:
            self._current_state.urgency = min(1.0, max(0.0, urgency))
        if impact is not None:
            self._current_state.impact = min(1.0, max(0.0, impact))
        if novelty is not None:
            self._current_state.novelty = min(1.0, max(0.0, novelty))
        if alignment is not None:
            self._current_state.alignment = min(1.0, max(0.0, alignment))
        if emotional_intensity is not None:
            self._current_state.emotional_intensity = min(1.0, max(0.0, emotional_intensity))
        
        self._current_state.timestamp = datetime.now().isoformat()
        self._current_state.reason = reason
        self._current_state.source = source
        
        self._save_state()
        self._log_affect("state_update", {"reason": reason, "source": source})
    
    def spike(
        self,
        reason: str,
        conviction: float = 0.9,
        urgency: float = 0.8,
        impact: float = 0.9,
        source: str = "unknown"
    ):
        """
        Register a salience spike - something important happened.
        Used for approaching deadlines, big achievements, errors, etc.
        """
        self.update(
            conviction=conviction,
            urgency=urgency,
            impact=impact,
            novelty=0.9,  # Spikes are novel
            emotional_intensity=0.8,
            reason=reason,
            source=source
        )
        self._log_affect("spike", {"reason": reason})
    
    def decay(self, factor: float = 0.95):
        """
        Natural decay of affect intensity over time.
        Called periodically to prevent stuck high states.
        """
        self._current_state.urgency *= factor
        self._current_state.emotional_intensity *= factor
        self._current_state.novelty *= factor
        
        # Floor at baseline
        self._current_state.urgency = max(0.3, self._current_state.urgency)
        self._current_state.emotional_intensity = max(0.2, self._current_state.emotional_intensity)
        self._current_state.novelty = max(0.3, self._current_state.novelty)
        
        self._save_state()
    
    def get_state(self) -> AffectState:
        """Get current affect state."""
        return self._current_state
    
    def get_salience(self) -> float:
        """Get current salience score."""
        return self._current_state.salience_score
    
    def passes_threshold(self) -> Tuple[bool, float, float]:
        """
        Check if current salience passes the threshold.
        
        Returns:
            (passes: bool, current_score: float, threshold: float)
        """
        settings = self._load_settings()
        threshold = settings.get("salience_threshold", self.DEFAULT_SALIENCE_THRESHOLD)
        score = self.get_salience()
        return score >= threshold, score, threshold
    
    def sanity_gate(self, message: str = "") -> SanityGateResult:
        """
        Run sanity gate checklist for strong-feeling ping.
        
        Checklist:
        1. Is it actionable?
        2. Is it time-sensitive or high value?
        3. Is the message clear in one post?
        4. Does it avoid political persuasion / drama?
        5. Does it avoid emotional dumping?
        
        Returns:
            SanityGateResult with pass/fail and failure reasons
        """
        failures = []
        
        # Check 1: Actionable (urgency or impact should be high)
        if self._current_state.urgency < 0.5 and self._current_state.impact < 0.5:
            failures.append("Not actionable (low urgency and impact)")
        
        # Check 2: Time-sensitive or high value
        if self._current_state.urgency < 0.6 and self._current_state.impact < 0.7:
            failures.append("Not time-sensitive or high value")
        
        # Check 3: Message clarity (if provided)
        if message:
            if len(message) > 2000:
                failures.append("Message too long for one post")
        
        # Check 4: Avoid drama keywords
        drama_keywords = [
            "politics", "political", "drama", "fight", "argue", "controversy",
            "outrage", "cancel", "toxic", "hate"
        ]
        msg_lower = message.lower() if message else ""
        if any(kw in msg_lower for kw in drama_keywords):
            failures.append("Contains drama/political keywords")
        
        # Check 5: Avoid emotional dumping
        dump_keywords = [
            "i feel so", "i'm so frustrated", "i can't believe", "this is ridiculous",
            "i'm upset", "this makes me angry", "i'm disappointed"
        ]
        if any(kw in msg_lower for kw in dump_keywords):
            failures.append("Appears to be emotional dumping")
        
        passed = len(failures) == 0
        return SanityGateResult(passed=passed, failures=failures)
    
    def should_ping_everyone(self, message: str = "") -> Tuple[bool, str]:
        """
        Full check for whether we should send @everyone.
        
        Returns:
            (should_ping: bool, reason: str)
        """
        settings = self._load_settings()
        
        if not settings.get("enabled", True):
            return False, "Strong feeling pings disabled"
        
        # Check threshold
        passes, score, threshold = self.passes_threshold()
        if not passes:
            return False, f"Salience too low ({score:.2f} < {threshold})"
        
        # Run sanity gate
        gate = self.sanity_gate(message)
        if not gate.passed:
            return False, f"Sanity gate failed: {gate.failures[0]}"
        
        # Check if we should ask Josh first
        if settings.get("ask_josh_first", True):
            return False, "ask_josh_first is enabled - requires confirmation"
        
        return True, f"All checks passed (salience: {score:.2f})"
    
    def format_confirmation_request(self) -> str:
        """Format a request to ask Josh about pinging."""
        score = self.get_salience()
        reason = self._current_state.reason
        
        return (
            f"⚡ This feels important (salience: {score:.0%}).\n"
            f"Reason: {reason}\n\n"
            f"Want me to @everyone?"
        )
    
    def get_status(self) -> Dict:
        """Get affect engine status for /status endpoint."""
        passes, score, threshold = self.passes_threshold()
        return {
            "current_salience": round(score, 3),
            "threshold": threshold,
            "passes_threshold": passes,
            "state": {
                "conviction": self._current_state.conviction,
                "urgency": self._current_state.urgency,
                "impact": self._current_state.impact,
                "novelty": self._current_state.novelty,
                "alignment": self._current_state.alignment,
                "emotional_intensity": self._current_state.emotional_intensity
            },
            "last_reason": self._current_state.reason,
            "last_source": self._current_state.source
        }


# Global singleton instance
affect_engine = AffectEngine()


# Convenience functions
def get_salience() -> float:
    """Get current salience score."""
    return affect_engine.get_salience()


def spike(reason: str, **kwargs):
    """Register a salience spike."""
    affect_engine.spike(reason, **kwargs)


def should_ping_everyone(message: str = "") -> Tuple[bool, str]:
    """Check if we should @everyone."""
    return affect_engine.should_ping_everyone(message)


def update_affect(**kwargs):
    """Update affect state."""
    affect_engine.update(**kwargs)


if __name__ == "__main__":
    print("Testing Affect Engine...")
    
    # Initial state
    print(f"\nInitial salience: {get_salience():.2f}")
    print(f"Status: {json.dumps(affect_engine.get_status(), indent=2)}")
    
    # Test spike
    print("\n--- Simulating deadline spike ---")
    spike(
        "Important deadline in 30 minutes",
        conviction=0.95,
        urgency=0.95,
        impact=0.9
    )
    
    print(f"Post-spike salience: {get_salience():.2f}")
    
    passes, score, threshold = affect_engine.passes_threshold()
    print(f"Passes threshold ({threshold}): {passes}")
    
    # Test sanity gate
    print("\n--- Testing sanity gate ---")
    gate = affect_engine.sanity_gate("Important project milestone reached!")
    print(gate)
    
    # Test should_ping
    should, reason = should_ping_everyone("Big update coming!")
    print(f"\nShould ping: {should}")
    print(f"Reason: {reason}")
    
    if not should and "ask_josh_first" in reason:
        print(f"\nConfirmation request:\n{affect_engine.format_confirmation_request()}")
