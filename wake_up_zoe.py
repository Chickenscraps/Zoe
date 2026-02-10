import sys
import os
import time

# Add skill dir
SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT PERSONA SKILL")
sys.path.insert(0, SKILL_DIR)

from discord_bridge import discord_bridge

CHANNEL_ID = "1462568916692762687"

INTRO_MESSAGE = """⚡ **SYSTEM ONLINE** ⚡

Identity: Zoe (Clawdbot V2)
Status: Cogent & Online
Modules:
- [x] Mood Engine
- [x] Memory Core (Segregated)
- [x] Music Profiler
- [x] Culture Scanner

Hello, Josh. I see you. Ready to build? 👀"""

print("Sending intro...")
success = discord_bridge.send_message(INTRO_MESSAGE, channel_id=CHANNEL_ID)
if success:
    print("✅ Intro sent successfully.")
else:
    print("❌ Failed to send intro.")
