"""
Fallback Responder for Clawdbot
Degraded mode responses when Gemini/primary LLM is unavailable.
Provides rule-based responses while maintaining personality.
"""
import os
import json
import random
from datetime import datetime
from typing import Optional, Dict, Any

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
FALLBACK_CACHE_FILE = os.path.join(SKILL_DIR, "fallback_cache.json")

# Rule-based response patterns
FALLBACK_RESPONSES = {
    "greeting": {
        "patterns": ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"],
        "responses": [
            "Hey! I'm in offline mode right now, but I'm still here for you.",
            "Hi there! My connection to the cloud is down, but I can still help with basics.",
            "Hello! Running in degraded mode, but still watching your back."
        ]
    },
    "status": {
        "patterns": ["how are you", "status", "what's up", "you okay"],
        "responses": [
            "I'm in offline mode - my primary brain is taking a break. But I'm still functional!",
            "Running on backup power, so to speak. Basic features still work.",
            "My AI core is temporarily unavailable, but notifications and memory are still running."
        ]
    },
    "help": {
        "patterns": ["help", "what can you do", "commands"],
        "responses": [
            "In offline mode, I can: check your calendar, read emails, sweep files, set reminders, and log notes. Just can't do deep thinking right now.",
            "Limited mode active. I can still handle: calendar, email, file sweeps, reminders. No AI chat until I reconnect."
        ]
    },
    "calendar": {
        "patterns": ["calendar", "schedule", "meeting", "events"],
        "responses": [
            "Let me check your calendar...",
            "Pulling up your schedule..."
        ],
        "action": "check_calendar"
    },
    "email": {
        "patterns": ["email", "inbox", "mail"],
        "responses": [
            "Checking your inbox...",
            "Let me look at your emails..."
        ],
        "action": "check_email"
    },
    "sweep": {
        "patterns": ["sweep", "clean", "organize", "desktop"],
        "responses": [
            "I can start a desktop sweep for you. Say 'confirm' to proceed.",
            "Ready to clean up. Just need your confirmation."
        ]
    },
    "affirm": {
        "patterns": ["thanks", "thank you", "good job", "nice"],
        "responses": [
            "You're welcome! Even in offline mode, I've got you.",
            "Happy to help, even when I'm not at full power!",
            "Anytime! I'll be back to full strength soon."
        ]
    }
}

# Offline status messages
OFFLINE_STATUS = {
    "brief": "I'm in offline mode right now.",
    "detailed": "My primary AI core (Gemini) is temporarily unavailable. I'm running on backup rules, but I can still help with basic tasks like calendar, email, file sweeps, and reminders.",
    "apologetic": "Sorry, can't think deeply right now - my brain is offline. But I'm still watching your deck!"
}


def _load_cache() -> Dict:
    """Load cached responses from previous successful AI calls."""
    try:
        with open(FALLBACK_CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"responses": {}, "last_updated": None}


def _save_cache(cache: Dict):
    """Save response cache."""
    cache["last_updated"] = datetime.now().isoformat()
    with open(FALLBACK_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def cache_successful_response(query: str, response: str):
    """Cache a successful AI response for similar future queries."""
    cache = _load_cache()
    # Simple key: first 50 chars of query, lowercased
    key = query.lower()[:50].strip()
    cache["responses"][key] = {
        "response": response,
        "cached_at": datetime.now().isoformat()
    }
    # Keep cache size reasonable
    if len(cache["responses"]) > 100:
        # Remove oldest entries
        sorted_keys = sorted(
            cache["responses"].keys(),
            key=lambda k: cache["responses"][k].get("cached_at", "")
        )
        for old_key in sorted_keys[:20]:
            del cache["responses"][old_key]
    _save_cache(cache)


def _find_cached_response(query: str) -> Optional[str]:
    """Find a cached response for similar query."""
    cache = _load_cache()
    key = query.lower()[:50].strip()
    if key in cache["responses"]:
        return cache["responses"][key]["response"]
    return None


def _match_pattern(text: str, patterns: list) -> bool:
    """Check if text matches any pattern."""
    text_lower = text.lower()
    return any(p in text_lower for p in patterns)


def get_fallback_response(query: str, context: Dict[str, Any] = None) -> str:
    """
    Get a fallback response when primary AI is unavailable.
    
    Args:
        query: User's query text
        context: Optional context dict with mode, state, etc.
    
    Returns:
        A rule-based response or cached response
    """
    query_lower = query.lower()
    
    # Try cached response first
    cached = _find_cached_response(query)
    if cached:
        return f"[Offline - from cache] {cached}"
    
    # Match against rule patterns
    for category, data in FALLBACK_RESPONSES.items():
        if _match_pattern(query, data["patterns"]):
            response = random.choice(data["responses"])
            
            # Handle special actions
            if data.get("action") == "check_calendar":
                try:
                    from read_calendar import get_upcoming_events
                    events = get_upcoming_events(max_results=3)
                    return f"{response}\n{events}"
                except Exception as e:
                    return f"{response} (Error: {e})"
            
            elif data.get("action") == "check_email":
                try:
                    from read_email import get_recent_emails
                    emails = get_recent_emails(max_results=3)
                    return f"{response}\n{emails}"
                except Exception as e:
                    return f"{response} (Error: {e})"
            
            return response
    
    # Default offline response
    return random.choice([
        f"I'm in offline mode and can't fully process that. {OFFLINE_STATUS['brief']}",
        f"{OFFLINE_STATUS['apologetic']} Try: calendar, email, sweep, or status.",
        f"My AI brain is napping, but I heard you. {OFFLINE_STATUS['brief']} Basic commands still work!"
    ])


def get_offline_status(detailed: bool = False) -> str:
    """Get current offline status message."""
    return OFFLINE_STATUS["detailed"] if detailed else OFFLINE_STATUS["brief"]


def is_degraded_mode() -> bool:
    """Check if we're currently in degraded mode."""
    try:
        from resilience import gemini_breaker
        return gemini_breaker.state == "OPEN"
    except ImportError:
        return False


if __name__ == "__main__":
    # Test
    print("Testing Fallback Responder...")
    
    test_queries = [
        "hello",
        "how are you?",
        "what's on my calendar?",
        "help me",
        "explain quantum physics",
        "thanks!"
    ]
    
    for q in test_queries:
        print(f"\nQ: {q}")
        print(f"A: {get_fallback_response(q)}")
