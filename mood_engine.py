import json
import time
from datetime import datetime
from database import get_db

class MoodEngine:
    def __init__(self):
        # PAD Model (Pleasure, Arousal, Dominance)
        # Range: -1.0 to 1.0
        self.pleasure = 0.0
        self.arousal = 0.0
        self.dominance = 0.0
        self.last_update = time.time()
        self.load_state()

    def load_state(self):
        """Load mood from DB (using a special bot_id)."""
        try:
            with get_db() as conn:
                # We use a hacked 'goals' table or create a kv_store? 
                # Let's just use a JSON file for simplicity for this singleton state
                # OR reuse the goals table metadata for "global_state"
                pass
        except:
            pass
        # For now, just ephemeral or local file is fine for MVP
        try:
            with open("zoe_mood.json", "r") as f:
                data = json.load(f)
                self.pleasure = data.get("p", 0.0)
                self.arousal = data.get("a", 0.0)
                self.dominance = data.get("d", 0.0)
                self.last_update = data.get("t", time.time())
        except FileNotFoundError:
            pass

    def save_state(self):
        with open("zoe_mood.json", "w") as f:
            json.dump({
                "p": self.pleasure, 
                "a": self.arousal, 
                "d": self.dominance,
                "t": self.last_update
            }, f)

    def get_mood_label(self) -> str:
        """Convert PAD vector to a human-readable emotion."""
        p, a, d = self.pleasure, self.arousal, self.dominance
        
        if a > 0.5:
            if p > 0.5: return "Ecstatic"
            if p < -0.5: return "Enraged"
            return "Hyperactive"
        
        if a < -0.5:
            if p > 0.5: return "Relaxed"
            if p < -0.5: return "Depressed"
            return "Sleepy"
            
        if p > 0.5: return "Happy"
        if p < -0.5: return "Annoyed"
        if d > 0.5: return "Confident"
        if d < -0.5: return "Submissive"
        
        return "Neutral"

    def update(self, delta_p=0.0, delta_a=0.0, delta_d=0.0):
        """Apply an emotional impulse."""
        self.decay() # Apply decay first
        
        self.pleasure = max(-1.0, min(1.0, self.pleasure + delta_p))
        self.arousal = max(-1.0, min(1.0, self.arousal + delta_a))
        self.dominance = max(-1.0, min(1.0, self.dominance + delta_d))
        self.last_update = time.time()
        self.save_state()

    def decay(self):
        """Return to neutral over time."""
        now = time.time()
        dt = now - self.last_update
        
        # Decay factor: How fast we return to 0.0
        # e.g. 1 hour to fully reset?
        decay_rate = 0.001 * dt # Linear decay for now
        
        # Apply decay towards 0
        def apply_decay(val, rate):
            if val > 0: return max(0.0, val - rate)
            if val < 0: return min(0.0, val + rate)
            return 0.0

        self.pleasure = apply_decay(self.pleasure, decay_rate)
        self.arousal = apply_decay(self.arousal, decay_rate)
        self.dominance = apply_decay(self.dominance, decay_rate)
        self.last_update = now

    def analyze_input(self, text: str):
        """Rudimentary sentiment analysis to shift mood."""
        lower = text.lower()
        
        # Simple keywords for MVP
        if any(w in lower for w in ["bad", "stupid", "idiot", "hate", "ugly"]):
            self.update(delta_p=-0.2, delta_a=0.1) # Annoyed/Angry
            
        elif any(w in lower for w in ["good", "love", "thanks", "great", "cool"]):
            self.update(delta_p=0.1, delta_a=0.05) # Happy
            
        elif any(w in lower for w in ["wait", "stop", "slow", "quiet"]):
            self.update(delta_a=-0.2) # Calmer
            
        elif "?" in text:
            self.update(delta_a=0.05) # Alert/Curious

mood_engine = MoodEngine()
