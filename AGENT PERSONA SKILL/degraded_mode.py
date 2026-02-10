"""
Degraded Mode Responder for Clawdbot
Fallback responses when Gemini/AI is unavailable.
"""
import os
import json
import random
import time
from datetime import datetime
from typing import Dict, Optional, Any, List

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

# Cached persona for offline mode
CACHED_PERSONA = None

# Rule-based response patterns
RESPONSE_PATTERNS = {
    # Greetings
    "hello": [
        "Hey! I'm running in offline mode right now, but I'm still here!",
        "Hi there! My brain's a bit fuzzy at the moment, but I can still help with basics.",
        "Hello! Running on backup systems - what do you need?"
    ],
    "how are you": [
        "Running on backup power, but still kicking! What can I do?",
        "I'm in offline mode, so not at 100%, but I'm here for you!",
        "Surviving! The AI servers are having a moment, but I'm still functional."
    ],
    "help": [
        "I'm in offline mode, so I can't think as deeply right now. But I can still:\n- Check your calendar\n- Look at your screen\n- Set reminders\n- Log notes",
        "My AI brain is taking a break. I can still do system tasks and basic commands though!",
        "Offline mode active. Try simple commands like 'check calendar' or 'look at screen'."
    ],
    
    # System tasks (still work offline)
    "calendar": "Let me check your calendar... (Running calendar check)",
    "screen": "I'll take a look at your screen... (Activating vision)",
    "email": "Checking your emails... (Running email check)",
    "desktop": "Looking at your desktop... (Scanning files)",
    
    # Error/unknown
    "default": [
        "I'm in offline mode right now - the AI service is temporarily unavailable. I can still do basic system tasks!",
        "My thinking cap is taking a break. Try again in a moment, or ask me to do something simpler!",
        "Running on backup - I can't process complex requests right now, but I'm still watching your deck!"
    ]
}

# System tasks that work in offline mode
OFFLINE_CAPABLE_TASKS = [
    "calendar", "email", "screen", "vision", "desktop", "sweep",
    "tasks", "drive", "files", "remind", "timer", "note"
]

def load_cached_persona() -> Dict:
    """Load cached persona for offline mode."""
    global CACHED_PERSONA
    
    if CACHED_PERSONA:
        return CACHED_PERSONA
    
    persona_path = os.path.join(SKILL_DIR, "persona.json")
    try:
        with open(persona_path, "r") as f:
            CACHED_PERSONA = json.load(f)
    except FileNotFoundError:
        CACHED_PERSONA = {
            "name": "Mr Gagger",
            "role": "Executive Ops Partner",
            "tone": "Helpful"
        }
    
    return CACHED_PERSONA

def get_offline_response(user_input: str) -> str:
    """
    Generate a response in offline/degraded mode.
    Uses pattern matching and cached persona.
    """
    text_lower = user_input.lower()
    persona = load_cached_persona()
    
    # Check for specific patterns
    for pattern, responses in RESPONSE_PATTERNS.items():
        if pattern == "default":
            continue
        if pattern in text_lower:
            if isinstance(responses, list):
                return random.choice(responses)
            return responses
    
    # Default response
    default_responses = RESPONSE_PATTERNS["default"]
    return random.choice(default_responses)

def is_offline_capable(user_input: str) -> bool:
    """Check if the request can be handled offline."""
    text_lower = user_input.lower()
    return any(task in text_lower for task in OFFLINE_CAPABLE_TASKS)

def get_degraded_status() -> Dict:
    """Get current degraded mode status."""
    try:
        from resilience import gemini_breaker
        return {
            "in_degraded_mode": gemini_breaker.state == "OPEN",
            "circuit_state": gemini_breaker.state,
            "failures": gemini_breaker.failures,
            "recovery_in": max(0, 
                gemini_breaker.recovery_timeout - 
                (time.time() - gemini_breaker.last_failure_time)
            ) if gemini_breaker.state == "OPEN" else 0
        }
    except Exception:
        return {"in_degraded_mode": False, "circuit_state": "UNKNOWN"}

class DegradedModeResponder:
    """
    Handles responses when the AI service is unavailable.
    Still processes system tasks, logs requests, and notifies user.
    """
    
    def __init__(self):
        self.persona = load_cached_persona()
        self.pending_requests = []
        self.is_active = False
    
    def activate(self, reason: str = "Service unavailable"):
        """Activate degraded mode."""
        self.is_active = True
        
        try:
            from event_bus import event_bus, Event, EventType, Urgency
            
            event = Event(
                event_type=EventType.SYSTEM_ERROR.value,
                payload={
                    "error": "AI service unavailable",
                    "reason": reason,
                    "mode": "degraded"
                },
                source="degraded_mode"
            )
            event_bus.publish(event)
            
            # Notify user
            event_bus.publish_agent_wants_user(
                title="Running on Backup",
                message="My AI brain is taking a break. I can still do system tasks!",
                urgency=Urgency.NORMAL,
                source="degraded_mode"
            )
        except ImportError:
            pass
        
        # Log activation
        try:
            from structured_logger import logger
            logger.warn("degraded_mode.activated", f"Reason: {reason}")
        except ImportError:
            print(f"[DegradedMode] Activated: {reason}")
    
    def deactivate(self):
        """Deactivate degraded mode."""
        self.is_active = False
        
        try:
            from structured_logger import logger
            logger.info("degraded_mode.deactivated", "AI service restored")
        except ImportError:
            print("[DegradedMode] Deactivated - AI restored")
    
    def respond(self, user_input: str) -> str:
        """
        Generate a response in degraded mode.
        Logs the request for later processing if needed.
        """
        # Log the request
        self.pending_requests.append({
            "timestamp": datetime.now().isoformat(),
            "input": user_input
        })
        
        # Check if this is a system task
        if is_offline_capable(user_input):
            # Return indicator that system should route to dispatcher
            return f"__ROUTE_TO_DISPATCHER__:{user_input}"
        
        # Return offline response
        return get_offline_response(user_input)
    
    def get_pending_requests(self) -> List:
        """Get requests that were queued during degraded mode."""
        return self.pending_requests
    
    def clear_pending(self):
        """Clear pending requests after processing."""
        self.pending_requests = []

# Need datetime for logging
from datetime import datetime
from typing import List
import time

# Global instance
degraded_responder = DegradedModeResponder()

if __name__ == "__main__":
    # Test
    print("Testing Degraded Mode Responder...")
    
    print(f"\nPersona: {load_cached_persona()['name']}")
    
    test_inputs = [
        "Hello!",
        "How are you?",
        "Can you help me?",
        "Check my calendar",
        "What is the meaning of life?"
    ]
    
    for inp in test_inputs:
        print(f"\n> {inp}")
        print(f"< {get_offline_response(inp)}")
        print(f"  Offline capable: {is_offline_capable(inp)}")
