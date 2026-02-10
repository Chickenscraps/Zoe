"""
TTS Engine for Clawdbot
Enhanced edge-tts wrapper with mood-dependent voice profiles and phrase banks.
"""
import os
import subprocess
import random
from typing import Dict, Optional, List
from enum import Enum

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
SPEECH_OUTPUT = os.path.join(SKILL_DIR, "last_speech.mp3")

# Voice profiles - feminine voices with different characteristics
VOICE_PROFILES = {
    "playful": {
        "voices": ["en-US-AvaNeural", "en-US-EmmaNeural", "en-GB-SoniaNeural"],
        "rate_range": (0, 15),   # +0% to +15%
        "pitch_range": (0, 5),   # +0Hz to +5Hz
    },
    "calm": {
        "voices": ["en-US-JennyNeural", "en-GB-LibbyNeural", "en-AU-NatashaNeural"],
        "rate_range": (-10, 0),  # -10% to 0%
        "pitch_range": (-3, 0),  # -3Hz to 0Hz
    },
    "focused": {
        "voices": ["en-US-AriaNeural", "en-US-SaraNeural"],
        "rate_range": (5, 15),   # +5% to +15%
        "pitch_range": (-2, 2),  # -2Hz to +2Hz
    },
    "silent": {
        "voices": [],
        "rate_range": (0, 0),
        "pitch_range": (0, 0),
    }
}

# Phrase banks by intent
PHRASE_BANKS = {
    "affirmation": {
        "playful": [
            "You're crushing it! 💪",
            "Look at you go!",
            "That's what I'm talking about!",
            "Okay, I see you! 👀",
            "Main character energy right there.",
            "Slay.",
            "We love to see it!"
        ],
        "calm": [
            "Great work.",
            "Well done.",
            "That was handled well.",
            "Nice job.",
            "Solid progress."
        ],
        "focused": [
            "Done.",
            "Complete.",
            "Task finished.",
            "Executed.",
            "Moving on."
        ]
    },
    "nudge": {
        "playful": [
            "Hey you! Still focused? 👀",
            "Psst... vibe check?",
            "Just checking in! Everything good?",
            "Quick status update for me?",
            "You've been quiet... miss me?"
        ],
        "calm": [
            "How are you doing?",
            "Need anything from me?",
            "Ready to continue when you are.",
            "I'm here if you need me."
        ],
        "focused": [
            "Status?",
            "Next task?",
            "Update.",
            "Ready for next item."
        ]
    },
    "question": {
        "playful": [
            "Wait, run that back—",
            "Okay but WHY though?",
            "I need the full lore on this.",
            "Spill! What's the context?"
        ],
        "calm": [
            "Could you clarify that?",
            "What would you like me to do?",
            "Can you tell me more?"
        ],
        "focused": [
            "Clarify.",
            "Specify.",
            "Details?"
        ]
    },
    "failure": {
        "playful": [
            "Okay that didn't work... but we got this!",
            "Ope! Let me try again.",
            "Well THAT happened. Round 2?",
            "Minor setback, major comeback energy."
        ],
        "calm": [
            "There was an issue. Let me retry.",
            "Something went wrong. Working on it.",
            "I'll try again."
        ],
        "focused": [
            "Error. Retrying.",
            "Failed. Attempting recovery.",
            "Issue detected."
        ]
    },
    "startup": {
        "playful": [
            "I'm awake! What are we getting into today?",
            "Good morning! Ready to be productive... or chaotic. Your call!",
            "Online and caffeinated. Let's go!"
        ],
        "calm": [
            "Good morning. I'm here when you need me.",
            "System online. Ready to assist.",
            "Hello. How can I help today?"
        ],
        "focused": [
            "Systems online.",
            "Ready.",
            "Operational."
        ]
    },
    "goodbye": {
        "playful": [
            "Later! Don't do anything I wouldn't do. 😏",
            "See ya! I'll be here, silently judging your file organization.",
            "Peace! ✌️"
        ],
        "calm": [
            "Goodbye. Rest well.",
            "Take care.",
            "Until next time."
        ],
        "focused": [
            "Session ended.",
            "Closing.",
            "Bye."
        ]
    }
}

class TTSEngine:
    """
    Enhanced TTS engine with mood-aware voice selection and phrase banks.
    Uses edge-tts for speech synthesis.
    """
    
    def __init__(self):
        self.current_style = "playful"
        self._session_voice = None  # Deterministic voice for session
    
    def set_style(self, style: str):
        """Set the current TTS style (playful, calm, focused, silent)."""
        if style in VOICE_PROFILES:
            self.current_style = style
            self._session_voice = None  # Reset session voice on style change
    
    def _get_voice(self) -> str:
        """Get voice for current style."""
        profile = VOICE_PROFILES.get(self.current_style, VOICE_PROFILES["playful"])
        voices = profile.get("voices", [])
        
        if not voices:
            return None  # Silent mode
        
        # Use session voice for consistency, or pick new one
        if self._session_voice and self._session_voice in voices:
            return self._session_voice
        
        self._session_voice = random.choice(voices)
        return self._session_voice
    
    def _get_rate_pitch(self, mood_modifiers: Dict = None) -> tuple:
        """Get rate and pitch with optional mood modifiers."""
        profile = VOICE_PROFILES.get(self.current_style, VOICE_PROFILES["playful"])
        
        rate_min, rate_max = profile.get("rate_range", (0, 0))
        pitch_min, pitch_max = profile.get("pitch_range", (0, 0))
        
        base_rate = random.randint(rate_min, rate_max)
        base_pitch = random.randint(pitch_min, pitch_max)
        
        # Apply mood modifiers if provided
        if mood_modifiers:
            rate_mod = mood_modifiers.get("rate_modifier", 1.0)
            pitch_mod = mood_modifiers.get("pitch_modifier", 0)
            
            # Convert rate modifier to percentage adjustment
            rate_adjustment = int((rate_mod - 1.0) * 100)
            base_rate += rate_adjustment
            base_pitch += pitch_mod
        
        # Clamp values
        base_rate = max(-20, min(30, base_rate))
        base_pitch = max(-10, min(10, base_pitch))
        
        return (f"{base_rate:+}%", f"{base_pitch:+}Hz")
    
    def get_phrase(self, intent: str) -> Optional[str]:
        """Get a random phrase for the given intent and current style."""
        intent_bank = PHRASE_BANKS.get(intent, {})
        style_phrases = intent_bank.get(self.current_style, intent_bank.get("playful", []))
        
        if style_phrases:
            return random.choice(style_phrases)
        return None
    
    def speak(
        self,
        text: str,
        mood_modifiers: Dict = None,
        blocking: bool = False,
        output_path: str = None
    ) -> bool:
        """
        Speak the given text using edge-tts.
        
        Args:
            text: Text to speak
            mood_modifiers: Optional dict with rate_modifier and pitch_modifier
            blocking: If True, wait for speech to complete
            output_path: Optional custom output path for MP3
        
        Returns:
            True if speech was initiated, False otherwise
        """
        if self.current_style == "silent":
            return False
        
        voice = self._get_voice()
        if not voice:
            return False
        
        rate, pitch = self._get_rate_pitch(mood_modifiers)
        
        # Sanitize text
        safe_text = text.replace('"', '').replace("'", "").replace("\n", " ").strip()
        if not safe_text:
            return False
        
        # Output path
        mp3_path = output_path or SPEECH_OUTPUT
        
        # Build command
        tts_cmd = f'edge-tts --voice {voice} --rate={rate} --pitch={pitch} --text "{safe_text}" --write-media "{mp3_path}"'
        
        if blocking:
            # Run TTS and wait
            result = subprocess.run(tts_cmd, shell=True, capture_output=True)
            if result.returncode == 0:
                # Play the audio
                play_cmd = f'start "" "{mp3_path}"'
                subprocess.run(play_cmd, shell=True)
                return True
            return False
        else:
            # Non-blocking: generate and play
            full_cmd = f'{tts_cmd} && start "" "{mp3_path}"'
            subprocess.Popen(full_cmd, shell=True)
            return True
    
    def speak_intent(
        self,
        intent: str,
        fallback_text: str = None,
        mood_modifiers: Dict = None
    ) -> bool:
        """
        Speak a phrase for the given intent.
        Uses phrase bank, falls back to fallback_text if no phrases available.
        """
        phrase = self.get_phrase(intent)
        if phrase:
            return self.speak(phrase, mood_modifiers)
        elif fallback_text:
            return self.speak(fallback_text, mood_modifiers)
        return False
    
    def speak_with_mood(self, text: str) -> bool:
        """
        Speak text with automatic mood engine integration.
        Gets mood modifiers from the mood engine if available.
        """
        try:
            from mood_engine import mood_engine
            modifiers = mood_engine.get_voice_modifiers()
            return self.speak(text, mood_modifiers=modifiers)
        except ImportError:
            return self.speak(text)

# Global singleton instance
tts_engine = TTSEngine()

# Convenience functions
def speak(text: str, mood_modifiers: Dict = None) -> bool:
    """Speak text using the global TTS engine."""
    return tts_engine.speak(text, mood_modifiers)

def speak_intent(intent: str, fallback: str = None) -> bool:
    """Speak a phrase for the given intent."""
    return tts_engine.speak_intent(intent, fallback)

def set_style(style: str):
    """Set the TTS style."""
    tts_engine.set_style(style)

if __name__ == "__main__":
    # Test
    print("Testing TTS Engine...")
    
    tts_engine.set_style("playful")
    print(f"Voice: {tts_engine._get_voice()}")
    print(f"Rate/Pitch: {tts_engine._get_rate_pitch()}")
    
    print("\nPhrase bank samples:")
    for intent in ["affirmation", "nudge", "question", "failure", "startup"]:
        print(f"  {intent}: {tts_engine.get_phrase(intent)}")
    
    # Speak test
    print("\nSpeaking test phrase...")
    tts_engine.speak("Hello! TTS engine is working.", blocking=True)
