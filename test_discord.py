"""
Test script for Discord proactive messaging.
Run this to verify Mr Gagger can send messages to Discord.
"""
import sys
import os

# Add the skill directory to path
SKILL_DIR = os.path.join(os.path.dirname(__file__), "AGENT PERSONA SKILL")
sys.path.insert(0, SKILL_DIR)

from notification_router import push_to_discord

if __name__ == "__main__":
    print("Testing Discord proactive messaging...")
    print("Sending test message to Discord channel 1470130507118280856...")
    
    result = push_to_discord("🔔 **Mr Gagger Test**: I can now reach out proactively on Discord! 🎉")
    
    if result:
        print("✅ SUCCESS: Message sent to Discord!")
    else:
        print("❌ FAILED: Could not send message to Discord.")
        print("Check that:")
        print("  1. discord.py and aiohttp are installed")
        print("  2. Discord token is in ~/.openclaw/openclaw.json")
        print("  3. Channel ID 1470130507118280856 is correct")
