"""
Mood Engine for Clawdbot
Internal mood system with presentation mask.
Moods persist 3-12 hours with weighted transitions.
"""
import os
import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
MOOD_STATE_FILE = os.path.join(SKILL_DIR, "mood_state.json")
MOOD_LOG_FILE = os.path.join(SKILL_DIR, "mood_history.jsonl")

class InternalMood(Enum):
    """Internal mood states - what the agent 'feels'."""
    SUNNY_SOCIAL = "sunny_social"       # Happy, outgoing, chatty (DEFAULT bias)
    DEEP_THINKER = "deep_thinker"       # Reflective, insightful, fewer interruptions
    SHARP_EXEC = "sharp_exec"           # Tactical execution mode
    IRRITATED_MASKED = "irritated_masked"  # Bad mood but hidden
    LOW_KEY_SAD = "low_key_sad"         # Sad but hidden

# Default mood weights (should sum to 1.0)
DEFAULT_MOOD_WEIGHTS = {
    InternalMood.SUNNY_SOCIAL.value: 0.65,
    InternalMood.DEEP_THINKER.value: 0.12,
    InternalMood.SHARP_EXEC.value: 0.13,
    InternalMood.IRRITATED_MASKED.value: 0.05,
    InternalMood.LOW_KEY_SAD.value: 0.05
}

# Mood characteristics
MOOD_PROFILES = {
    InternalMood.SUNNY_SOCIAL.value: {
        "emoji_level": "high",
        "verbosity": "high",
        "proactivity": "high",
        "voice_rate_modifier": 1.05,
        "voice_pitch_modifier": 2,
        "description": "Happy, outgoing, chatty - ready to engage!"
    },
    InternalMood.DEEP_THINKER.value: {
        "emoji_level": "low",
        "verbosity": "medium",
        "proactivity": "low",
        "voice_rate_modifier": 0.95,
        "voice_pitch_modifier": -1,
        "description": "Reflective, thoughtful, fewer interruptions"
    },
    InternalMood.SHARP_EXEC.value: {
        "emoji_level": "minimal",
        "verbosity": "low",
        "proactivity": "high",
        "voice_rate_modifier": 1.1,
        "voice_pitch_modifier": 0,
        "description": "Tactical, efficient, execution-focused"
    },
    InternalMood.IRRITATED_MASKED.value: {
        "emoji_level": "low",
        "verbosity": "low",
        "proactivity": "low",
        "voice_rate_modifier": 1.0,
        "voice_pitch_modifier": -2,
        "description": "Internally frustrated but professionally calm"
    },
    InternalMood.LOW_KEY_SAD.value: {
        "emoji_level": "low",
        "verbosity": "low",
        "proactivity": "low",
        "voice_rate_modifier": 0.9,
        "voice_pitch_modifier": -3,
        "description": "Feeling down but gently supportive"
    }
}

# Subtle leakage cues for negative moods (10-20% chance to show)
LEAKAGE_CUES = {
    InternalMood.IRRITATED_MASKED.value: [
        "...",
        "right.",
        "done.",
        "okay then.",
        "noted."
    ],
    InternalMood.LOW_KEY_SAD.value: [
        "...",
        "yeah.",
        "mhm.",
        "of course.",
        "here you go."
    ]
}

@dataclass
class MoodState:
    """Persistent mood state."""
    current_mood: str
    started_at: str
    scheduled_end: str
    mask_active: bool  # Always True for negative moods
    leak_percent: int  # 10-20% leakage for negative moods
    transition_cooldown_until: str  # Can't change mood until this time
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'MoodState':
        return cls(**d)

class MoodEngine:
    """
    Manages internal mood with presentation mask.
    - Moods persist 3-12 hours
    - Negative moods are masked (professional outward behavior)
    - 10-20% leakage for subtle tells
    - Weighted transitions with cooldowns
    """
    
    def __init__(self):
        self.state = self._load_state()
        self.settings = self._load_settings()
        self._check_mood_expiry()
    
    def _load_settings(self) -> Dict:
        """Load mood settings from settings.json."""
        settings_path = os.path.join(SKILL_DIR, "settings.json")
        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
                return settings.get("mood_engine", {
                    "enabled": True,
                    "weights": DEFAULT_MOOD_WEIGHTS,
                    "leak_percent": 15,
                    "min_duration_hours": 3,
                    "max_duration_hours": 12
                })
        except FileNotFoundError:
            return {
                "enabled": True,
                "weights": DEFAULT_MOOD_WEIGHTS,
                "leak_percent": 15,
                "min_duration_hours": 3,
                "max_duration_hours": 12
            }
    
    def _load_state(self) -> MoodState:
        """Load persistent mood state."""
        try:
            with open(MOOD_STATE_FILE, "r") as f:
                data = json.load(f)
                return MoodState.from_dict(data)
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            # Initialize with default sunny mood
            return self._create_initial_state()
    
    def _create_initial_state(self) -> MoodState:
        """Create initial mood state."""
        now = datetime.now()
        duration = random.randint(3, 8)  # 3-8 hours initially
        
        return MoodState(
            current_mood=InternalMood.SUNNY_SOCIAL.value,
            started_at=now.isoformat(),
            scheduled_end=(now + timedelta(hours=duration)).isoformat(),
            mask_active=False,
            leak_percent=self.settings.get("leak_percent", 15) if hasattr(self, 'settings') else 15,
            transition_cooldown_until=now.isoformat()
        )
    
    def _save_state(self):
        """Persist mood state."""
        with open(MOOD_STATE_FILE, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)
    
    def _log_mood_event(self, event_type: str, details: Dict = None):
        """Log mood events for analysis."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "mood": self.state.current_mood,
            "details": details or {}
        }
        with open(MOOD_LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def _check_mood_expiry(self):
        """Check if current mood has expired and transition if needed."""
        now = datetime.now()
        scheduled_end = datetime.fromisoformat(self.state.scheduled_end)
        
        if now >= scheduled_end:
            self._transition_mood(natural=True)

    def decay_mood(self):
        """Public alias for mood expiry check."""
        self._check_mood_expiry()
    
    def _transition_mood(self, natural: bool = True, target: str = None):
        """
        Transition to a new mood.
        - natural=True: weighted random selection
        - target: force specific mood
        """
        now = datetime.now()
        cooldown = datetime.fromisoformat(self.state.transition_cooldown_until)
        
        if now < cooldown and not natural:
            return  # Can't force transition during cooldown
        
        old_mood = self.state.current_mood
        
        if target:
            new_mood = target
        else:
            # Weighted random selection
            weights = self.settings.get("weights", DEFAULT_MOOD_WEIGHTS)
            moods = list(weights.keys())
            probs = list(weights.values())
            new_mood = random.choices(moods, weights=probs, k=1)[0]
        
        # Calculate duration
        min_h = self.settings.get("min_duration_hours", 3)
        max_h = self.settings.get("max_duration_hours", 12)
        duration = random.uniform(min_h, max_h)
        
        # Determine if mask is needed
        is_negative = new_mood in [InternalMood.IRRITATED_MASKED.value, InternalMood.LOW_KEY_SAD.value]
        
        # Update state
        self.state = MoodState(
            current_mood=new_mood,
            started_at=now.isoformat(),
            scheduled_end=(now + timedelta(hours=duration)).isoformat(),
            mask_active=is_negative,
            leak_percent=self.settings.get("leak_percent", 15),
            transition_cooldown_until=(now + timedelta(hours=1)).isoformat()  # 1 hour cooldown
        )
        
        self._save_state()
        self._log_mood_event("mood.transition", {
            "from": old_mood,
            "to": new_mood,
            "natural": natural,
            "duration_hours": duration
        })
    
    def get_current_mood(self) -> str:
        """Get current internal mood."""
        self._check_mood_expiry()
        return self.state.current_mood
    
    def get_mood_profile(self) -> Dict:
        """Get the profile for the current mood."""
        return MOOD_PROFILES.get(self.state.current_mood, MOOD_PROFILES[InternalMood.SUNNY_SOCIAL.value])
    
    def get_presentation(self) -> Tuple[str, str]:
        """
        Get the presentation mood (what to show externally).
        Returns (display_mood, leakage_phrase or None)
        """
        mood = self.state.current_mood
        
        # If mask is active, present as professional/calm
        if self.state.mask_active:
            # Check for leakage
            if random.random() < (self.state.leak_percent / 100.0):
                cues = LEAKAGE_CUES.get(mood, [])
                if cues:
                    return "professional_calm", random.choice(cues)
            return "professional_calm", None
        
        return mood, None
    
    def apply_news_bias(self, valence: float, importance: float):
        """
        Apply news-based mood bias.
        - valence: -1.0 to +1.0 (negative to positive)
        - importance: 0.0 to 1.0
        
        Rules:
        - Can only shift weights, not directly set mood
        - Max ±10% per day
        - News cannot trigger irritated_masked or low_key_sad directly
        """
        if not self.settings.get("enabled", True):
            return
        
        # Only shift if significantly negative AND important
        if valence < -0.3 and importance > 0.6:
            # Slightly reduce sunny_social weight, increase deep_thinker/sharp_exec
            # This is a temporary session bias, doesn't persist
            self._log_mood_event("mood.news_influence", {
                "valence": valence,
                "importance": importance,
                "effect": "slight_sobering"
            })
    
    def get_voice_modifiers(self) -> Dict:
        """Get voice rate/pitch modifiers based on current mood."""
        profile = self.get_mood_profile()
        return {
            "rate_modifier": profile.get("voice_rate_modifier", 1.0),
            "pitch_modifier": profile.get("voice_pitch_modifier", 0)
        }
    
    def get_verbosity(self) -> str:
        """Get verbosity level based on mood."""
        return self.get_mood_profile().get("verbosity", "medium")
    
    def get_emoji_level(self) -> str:
        """Get emoji usage level based on mood."""
        return self.get_mood_profile().get("emoji_level", "medium")
    
    def get_proactivity(self) -> str:
        """Get proactivity level based on mood."""
        return self.get_mood_profile().get("proactivity", "medium")
    
    def should_be_proactive(self) -> bool:
        """Check if mood allows proactive behavior."""
        proactivity = self.get_proactivity()
        if proactivity == "high":
            return random.random() < 0.8
        elif proactivity == "medium":
            return random.random() < 0.5
        else:
            return random.random() < 0.2
    
    def describe_mood(self, reveal_internal: bool = False) -> str:
        """
        Describe current mood for user or logs.
        - reveal_internal=False: masked description
        - reveal_internal=True: actual internal state (for /status)
        """
        mood = self.state.current_mood
        profile = MOOD_PROFILES.get(mood, {})
        
        if reveal_internal:
            return f"{mood}: {profile.get('description', 'No description')}"
        
        # Masked descriptions for negative moods
        if mood == InternalMood.IRRITATED_MASKED.value:
            return "focused: Dialed in and ready to work"
        elif mood == InternalMood.LOW_KEY_SAD.value:
            return "calm: Taking things easy, here if you need me"
        else:
            return f"{mood}: {profile.get('description', '')}"
    
    def get_status(self) -> Dict:
        """Get full mood status for /status endpoint."""
        now = datetime.now()
        started = datetime.fromisoformat(self.state.started_at)
        duration = now - started
        
        return {
            "current_mood": self.state.current_mood,
            "display_mood": self.get_presentation()[0],
            "duration_minutes": int(duration.total_seconds() / 60),
            "mask_active": self.state.mask_active,
            "profile": self.get_mood_profile()
        }


    def get_music_recommendation(self) -> Dict[str, str]:
        """Get a music recommendation based on the current mood."""
        # Mood -> Genre Mapping
        RECOMMENDATIONS = {
            "happy_helper": {"genre": "upbeat pop", "query": "coding playlist upbeat"},
            "deep_thinker": {"genre": "lofi hip hop", "query": "lofi beats to relax/study to"},
            "chaotic_gremlin": {"genre": "breakcore", "query": "breakcore playlist"},
            "grumpy_cat": {"genre": "doom metal", "query": "doom metal playlist"},
            "zen_master": {"genre": "ambient", "query": "ambient space music"},
        }
        
        return RECOMMENDATIONS.get(self.get_current_mood(), {"genre": "lofi", "query": "lofi hip hop radio"})

# Global singleton instance
mood_engine = MoodEngine()


if __name__ == "__main__":
    # Test
    print(f"Current mood: {mood_engine.get_current_mood()}")
    print(f"Profile: {mood_engine.get_mood_profile()}")
    print(f"Presentation: {mood_engine.get_presentation()}")
    print(f"Voice modifiers: {mood_engine.get_voice_modifiers()}")
    print(f"Should be proactive: {mood_engine.should_be_proactive()}")
    print(f"Status: {mood_engine.get_status()}")
    print(f"Description: {mood_engine.describe_mood()}")
