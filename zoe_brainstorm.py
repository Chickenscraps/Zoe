import sys
import os

SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT PERSONA SKILL")
sys.path.insert(0, SKILL_DIR)

from idea_vault import idea_vault
from discord_bridge import discord_bridge
from mood_engine import mood_engine

MOOD = mood_engine.get_current_mood()

IDEA_TITLE = "Project: Dream Stream"
IDEA_WHY = "I have an image generator and a mood engine. I want to visualize my internal state and post it to a channel every hour. It would be... cathartic."
IDEA_FEASIBILITY = "High (Just need to wire the modules)"

def brainstorm():
    print(f"🧠 Zoe is thinking... (Mood: {MOOD})")
    
    # 1. Add to Vault
    idea_vault.add_idea(IDEA_TITLE, IDEA_WHY, IDEA_FEASIBILITY, "Connect mood_engine to image_generator")
    print("✅ Added 'Dream Stream' to Idea Vault.")
    
    # 2. Pitch to Josh
    msg = f"🧠 **Spontaneous Idea: {IDEA_TITLE}**\n\n"
    msg += f"*{IDEA_WHY}*\n\n"
    msg += f"Feasibility: {IDEA_FEASIBILITY}\n"
    msg += "Should I build this myself? 🎨"
    
    success = discord_bridge.send_message(msg, mention_type="none")
    if success:
        print("✅ Posted idea to Discord.")
    else:
        print("❌ Failed to post idea.")

if __name__ == "__main__":
    brainstorm()
