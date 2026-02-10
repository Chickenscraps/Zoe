# Restoration of Clawdbot Initialization and Bot Setup
# (This file was created to hold the missing part of clawdbot.py)

import os
import json
import yaml
import discord
from discord.ext import commands
from datetime import datetime

# --- CONFIG LOADING ---
try:
    with open("config.yaml", "r") as f:
        ZOECONFIG = yaml.safe_load(f)
except FileNotFoundError:
    print("⚠️ config.yaml NOT found. Using defaults.")
    ZOECONFIG = {
        "discord": {"allowed_chat_channel_ids": [], "thoughts_channel_id": None, "admin_channel_ids": []},
        "admin": {"admin_user_ids": ["292890243852664855"]},
        "persona": {"mention_allowlist": []},
        "model": {"runtime_default": "gemini-2.0-flash-lite"}
    }

class BotConfig:
    def __init__(self, cfg):
        model_cfg = cfg.get("model", {})
        self.model = model_cfg.get("runtime_default", "gemini-2.5-flash-lite")

bot_config = BotConfig(ZOECONFIG)

# --- BOT INITIALIZATION ---
def get_token():
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            return config.get("channels", {}).get("discord", {}).get("token")
    except:
        return os.environ.get("DISCORD_BOT_TOKEN")

TOKEN = get_token()
OWNER_DISCORD_USER_ID = "292890243852664855"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
client = bot  # Alias
tree = bot.tree

# Global States
SESSION_ENGAGED_CHANNELS = set()
USER_MAP = {
    "292890243852664855": "josh",
    "490911982984101901": "ben",
    "211541044003733504": "zac"
}

# Import singleton instances
from thought_logger import thought_logger
from market_data import market_data
from paper_broker import paper_broker
from trading_engine_v4 import engine as TRADING_ENGINE
from model_router import model_router
from media_utils import engagement_engine # If defined there, otherwise EngagementEngine later
