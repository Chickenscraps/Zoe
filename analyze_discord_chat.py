"""
Discord Chat Analyzer - Learn user personas from chat history
Analyzes Discord messages to understand Josh, Ben, and Zac's personalities
"""
import os
import json
import sys
from datetime import datetime
from collections import defaultdict

# Add skill directory to path
SKILL_DIR = os.path.join(os.path.dirname(__file__), "AGENT PERSONA SKILL")
sys.path.insert(0, SKILL_DIR)

# User IDs
USERS = {
    "292890243852664855": "Josh",
    "490911982984101901": "Ben",
    "211541044003733504": "Zac"
}

CHANNEL_ID = "799704432929406998"

def fetch_discord_messages(channel_id, limit=1000):
    """
    Fetch messages from Discord using OpenClaw CLI.
    Returns list of message objects.
    """
    import subprocess
    
    # Use OpenClaw to read Discord messages
    # This will use the discord-actions tool
    cmd = f'pnpm openclaw chat "Read the last {limit} messages from Discord channel {channel_id} and return them as JSON" --session "agent:main:main"'
    
    try:
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=60,
            shell=True
        )
        
        if result.returncode == 0:
            # Parse the response
            return json.loads(result.stdout)
        else:
            print(f"Error fetching messages: {result.stderr}")
            return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def analyze_user_messages(messages, user_id):
    """
    Analyze messages from a specific user to build their persona.
    """
    user_messages = [m for m in messages if m.get('author', {}).get('id') == user_id]
    
    persona = {
        "user_id": user_id,
        "name": USERS.get(user_id, "Unknown"),
        "message_count": len(user_messages),
        "common_phrases": [],
        "topics": [],
        "humor_style": "",
        "communication_style": "",
        "interests": [],
        "sample_messages": user_messages[:10]  # First 10 for reference
    }
    
    # TODO: Use Ollama to analyze the messages and extract patterns
    # For now, just return basic stats
    
    return persona

def save_personas(personas, output_file="user_personas.json"):
    """Save persona data to file."""
    output_path = os.path.join(SKILL_DIR, output_file)
    with open(output_path, "w") as f:
        json.dump(personas, f, indent=2)
    print(f"Personas saved to {output_path}")

if __name__ == "__main__":
    print("🔍 Analyzing Discord chat history...")
    print(f"Channel: {CHANNEL_ID}")
    print(f"Users: {', '.join(USERS.values())}")
    
    # Fetch messages
    print("\n📥 Fetching messages...")
    messages = fetch_discord_messages(CHANNEL_ID, limit=1000)
    
    if not messages:
        print("❌ No messages fetched. Using Discord API directly...")
        # TODO: Implement direct Discord API call
    
    # Analyze each user
    print("\n🧠 Analyzing user personas...")
    personas = {}
    for user_id, name in USERS.items():
        print(f"  Analyzing {name}...")
        personas[name] = analyze_user_messages(messages, user_id)
    
    # Save results
    save_personas(personas)
    
    print("\n✅ Analysis complete!")
    print(f"Total messages analyzed: {len(messages)}")
    for name, persona in personas.items():
        print(f"  {name}: {persona['message_count']} messages")
