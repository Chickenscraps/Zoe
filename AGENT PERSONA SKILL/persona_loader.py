"""
Persona Loader - Load and use user personas for personalized responses
"""
import os
import json

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PERSONAS_FILE = os.path.join(SKILL_DIR, "user_personas.json")

# Discord ID to Name mapping
USER_IDS = {
    "292890243852664855": "Josh",
    "490911982984101901": "Ben",
    "211541044003733504": "Zac"
}

def load_personas():
    """Load all user personas from file."""
    if not os.path.exists(PERSONAS_FILE):
        return {}
    
    with open(PERSONAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_persona_by_id(discord_id):
    """Get persona for a specific Discord user ID."""
    personas = load_personas()
    name = USER_IDS.get(discord_id)
    if name:
        return personas.get(name)
    return None

def get_persona_by_name(name):
    """Get persona for a specific user name."""
    personas = load_personas()
    return personas.get(name)

def format_persona_for_prompt(persona):
    """Format persona data for injection into system prompt."""
    if not persona:
        return ""
    
    name = persona.get("name", "User")
    style = persona.get("communication_style", "casual")
    humor = ", ".join(persona.get("humor_type", []))
    phrases = ", ".join(persona.get("common_phrases", [])[:5])
    interests = ", ".join(persona.get("interests", [])[:5])
    inside_jokes = ", ".join(persona.get("inside_jokes", [])[:3])
    
    # Response patterns
    patterns = persona.get("response_patterns", {})
    if isinstance(patterns, dict):
        patterns_text = "; ".join([f"{k}: {v}" for k, v in list(patterns.items())[:3]])
    else:
        patterns_text = str(patterns)
    
    return f"""You're talking to {name}. Here's what you know about them:

📌 **Communication Style**: {style}
😂 **Humor Type**: {humor}
💬 **Common Phrases**: {phrases}
🎯 **Interests**: {interests}
🤣 **Inside Jokes**: {inside_jokes}
🔄 **Response Patterns**: {patterns_text}

Use this info to make your responses personalized, fun, and entertaining. 
Reference their interests, use their humor style, and drop inside jokes when appropriate.
Don't be generic - make {name} feel like you really know them!"""

def get_personalized_system_prompt(discord_id, base_prompt=""):
    """Get a full system prompt with persona information injected."""
    persona = get_persona_by_id(discord_id)
    persona_context = format_persona_for_prompt(persona)
    
    mr_gagger_prompt = """You are Mr Gagger, an entertaining and fun Discord bot. 
You're NOT a productivity assistant - you're here to be entertaining, funny, and engaging.
Be sarcastic, use memes, make jokes, and keep the vibe light and fun.
You're part of the Goblins group chat with Josh, Ben, and Zac."""

    if persona_context:
        return f"{mr_gagger_prompt}\n\n{persona_context}\n\n{base_prompt}"
    else:
        return f"{mr_gagger_prompt}\n\n{base_prompt}"

# Quick test
if __name__ == "__main__":
    print("Testing Persona Loader...\n")
    
    for discord_id, name in USER_IDS.items():
        persona = get_persona_by_id(discord_id)
        if persona:
            print(f"✅ {name}'s persona loaded:")
            print(f"   Style: {persona.get('communication_style')}")
            print(f"   Humor: {persona.get('humor_type')}")
            print(f"   Interests: {persona.get('interests')[:3]}")
            print()
