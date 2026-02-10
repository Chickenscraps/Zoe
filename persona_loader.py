import os

def load_persona() -> str:
    """
    Load the SOUL.md file to define the agent's personality.
    """
    soul_path = os.path.join(os.path.dirname(__file__), "SOUL.md")
    
    if os.path.exists(soul_path):
        with open(soul_path, "r", encoding="utf-8") as f:
            return f.read()
            
    return "Identity: You are a helpful AI assistant."

def get_system_prompt(context: str = "") -> str:
    """
    Assemble the dynamic system prompt.
    """
    soul = load_persona()
    
    # Load Constitution
    try:
        from database_tool import get_constitution
        rules = get_constitution()
        rules_text = "\n".join([f"- {r}" for r in rules]) if rules else "- Be yourself."
    except:
        rules_text = "- No specific constitutional rules loaded."

    prompt = f"""
{soul}

## The Constitution (Immutable Rules)
{rules_text}

## Current Context
{context}

## Instructions
- Stay in character (Zoe).
- Use the provided context to inform your response.
- If you don't know something, ask or search.
"""
    return prompt

def get_user_context(profile: str) -> str:
    """Mock context function for now."""
    return f"User Profile: {profile}"

def get_voice_mode_instructions(mode: str = "standard") -> str:
    """Voice mode instructions."""
    return f"Voice Mode ({mode}): Short, conversational, no markdown."

def calculate_mood_tone(valence, romance_on=False, *args, **kwargs) -> str:
    """Mock mood tone."""
    return f"Analysis: Valence={valence}, Romance={romance_on}"

def get_time_aware_greeting() -> str:
    """Get greeting based on time."""
    from datetime import datetime
    h = datetime.now().hour
    if h < 12: return "Good morning."
    if h < 18: return "Good afternoon."
    return "Good evening."
