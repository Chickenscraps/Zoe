import discord
import os
import json
import asyncio

def load_config():
    """Load Discord token from openclaw.json."""
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    with open(config_path, "r") as f:
        config = json.load(f)
    return config.get("channels", {}).get("discord", {}).get("token")

TOKEN = load_config()

intents = discord.Intents.default()
# intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    with open("debug_guilds.txt", "w", encoding="utf-8") as f:
        f.write(f"Logged in as {client.user} (ID: {client.user.id})\n")
        f.write("Guilds:\n")
        for guild in client.guilds:
            f.write(f" - {guild.name} (ID: {guild.id})\n")
            f.write(f"   Channels:\n")
            for channel in guild.channels:
                f.write(f"     - {channel.name} ({channel.type}) ID: {channel.id}\n")
    
    await client.close()

client.run(TOKEN)
