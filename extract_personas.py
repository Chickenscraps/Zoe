"""
Persona Extractor - AI-powered personality analysis
Uses Llama 3.1 to analyze Discord messages and extract user personas
"""
import os
import json
import ollama
from collections import defaultdict

# User IDs
USERS = {
    "292890243852664855": "Josh",
    "490911982984101901": "Ben",
    "211541044003733504": "Zac"
}

SKILL_DIR = os.path.join(os.path.dirname(__file__), "AGENT PERSONA SKILL")
MODEL = "llama3.1"

def load_user_messages(user_name):
    """Load messages for a specific user."""
    filename = f"{user_name.lower()}_messages.json"
    filepath = os.path.join(SKILL_DIR, filename)
    
    if not os.path.exists(filepath):
        print(f"❌ {filename} not found")
        return []
    
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def analyze_messages_batch(messages, user_name, batch_size=50):
    """
    Analyze a batch of messages using Llama 3.1.
    Returns extracted persona insights.
    """
    # Take a sample of messages (spread across the conversation)
    total = len(messages)
    if total > batch_size:
        step = total // batch_size
        sample = [messages[i] for i in range(0, total, step)][:batch_size]
    else:
        sample = messages
    
    # Format messages for analysis
    message_text = "\n".join([
        f"[{msg.get('timestamp', 'unknown')}] {msg.get('content', '')}"
        for msg in sample
        if msg.get('content', '').strip()
    ])
    
    prompt = f"""Analyze these Discord messages from {user_name}. Extract their personality profile:

Messages:
{message_text}

Analyze and return a JSON object with:
1. communication_style: How they communicate (casual/formal/sarcastic/memey/etc)
2. humor_type: Types of humor they use/enjoy (list of strings)
3. common_phrases: Catchphrases, slang, emoji patterns (list of strings)
4. interests: Main topics they discuss (list of strings)
5. inside_jokes: Any recurring themes or jokes (list of strings)
6. response_patterns: How they typically respond to greetings, questions, roasts
7. preferences: What they like and dislike in conversations

Return ONLY valid JSON, no other text."""

    try:
        response = ollama.chat(
            model=MODEL,
            messages=[{
                'role': 'user',
                'content': prompt
            }]
        )
        
        result_text = response['message']['content'].strip()
        
        # Try to extract JSON from the response
        if result_text.startswith('```'):
            # Remove code block markers
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
        
        return json.loads(result_text)
    except Exception as e:
        print(f"Error analyzing {user_name}'s messages: {e}")
        return None

def create_persona_profile(user_id, user_name, messages):
    """
    Create a complete persona profile for a user.
    """
    print(f"\n🧠 Analyzing {user_name}'s personality...")
    print(f"   Messages to analyze: {len(messages)}")
    
    # Analyze messages
    analysis = analyze_messages_batch(messages, user_name)
    
    if not analysis:
        print(f"   ❌ Analysis failed for {user_name}")
        return None
    
    # Create persona profile
    persona = {
        "user_id": user_id,
        "name": user_name,
        "message_count": len(messages),
        "communication_style": analysis.get("communication_style", "unknown"),
        "humor_type": analysis.get("humor_type", []),
        "common_phrases": analysis.get("common_phrases", []),
        "interests": analysis.get("interests", []),
        "inside_jokes": analysis.get("inside_jokes", []),
        "response_patterns": analysis.get("response_patterns", {}),
        "preferences": analysis.get("preferences", {}),
        "last_updated": "2026-02-08T11:31:51-08:00"
    }
    
    print(f"   ✅ Persona extracted for {user_name}")
    return persona

def save_personas(personas):
    """Save all persona profiles to file."""
    output_file = os.path.join(SKILL_DIR, "user_personas.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(personas, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Personas saved to {output_file}")

def print_persona_summary(persona):
    """Print a summary of the persona."""
    print(f"\n{'='*60}")
    print(f"  {persona['name']}'s Persona")
    print(f"{'='*60}")
    print(f"  Messages analyzed: {persona['message_count']}")
    print(f"  Communication style: {persona['communication_style']}")
    print(f"  Humor types: {', '.join(persona['humor_type'][:3])}")
    print(f"  Top interests: {', '.join(persona['interests'][:3])}")
    print(f"  Common phrases: {', '.join(persona['common_phrases'][:3])}")

def main():
    """Main function."""
    print("🚀 Persona Extractor - AI-Powered Personality Analysis")
    print(f"Model: {MODEL}\n")
    
    personas = {}
    
    for user_id, user_name in USERS.items():
        # Load messages
        messages = load_user_messages(user_name)
        
        if not messages:
            print(f"⚠️  Skipping {user_name} - no messages found")
            continue
        
        # Create persona
        persona = create_persona_profile(user_id, user_name, messages)
        
        if persona:
            personas[user_name] = persona
            print_persona_summary(persona)
    
    if personas:
        # Save all personas
        save_personas(personas)
        
        print(f"\n✅ Complete! Created {len(personas)} persona profiles")
        print("\nNext step: Integrate personas with Mr Gagger")
        print("  The bot will now use these profiles for personalized responses!")
    else:
        print("\n❌ No personas created")
        print("\nMake sure you've run: python parse_discord_export.py <export_file.json>")

if __name__ == "__main__":
    main()
