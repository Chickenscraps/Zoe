"""
Discord Gateway Client for Clawdbot
Handles WebSocket connection, presence, and incoming message routing to server API.
"""
import os
import sys
import json
import asyncio
import aiohttp
import discord
from discord.ext import tasks

# Add skill dir to path
SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT PERSONA SKILL")
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

SERVER_URL = "http://localhost:8000"

def get_token():
    # Try env
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if token: return token
    
    # Try config
    try:
        config_path = os.path.expanduser("~/.openclaw/openclaw.json")
        with open(config_path, "r") as f:
            config = json.load(f)
            return config.get("channels", {}).get("discord", {}).get("token")
    except: return None

class ClawdbotClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
    async def on_ready(self):
        print(f"✅ Discord Gateway Connected as {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening, 
            name="/wsb show | Impress Mode"
        ))

    async def on_message(self, message):
        # Ignore self
        if message.author == self.user:
            return

        # Check for mention or DM
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mention = self.user in message.mentions
        
        if is_dm or is_mention:
            content = message.content.replace(f"<@{self.user.id}>", "").strip()
            if not content: return
            
            async with message.channel.typing():
                response = await self.forward_to_server(content, str(message.author.id))
                
            if response:
                await message.reply(response)

    async def forward_to_server(self, text, user_id):
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"message": text, "user_id": user_id}
                async with session.post(f"{SERVER_URL}/chat", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response")
                    else:
                        return f"⚠️ Server Error: {resp.status}"
        except Exception as e:
            return f"⚠️ Connection Error: {str(e)}"

if __name__ == "__main__":
    token = get_token()
    if not token:
        print("❌ No Discord Token Found!")
        sys.exit(1)
        
    print("🚀 Starting Discord Gateway Client...")
    client = ClawdbotClient()
    client.run(token)
