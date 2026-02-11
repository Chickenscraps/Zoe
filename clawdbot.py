"""
AGI-Lite Discord Bot - Main Entry Point
Clawdbot: 4th member of the Goblins group chat
"""
import os
import sys
import json
import asyncio
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Dict, Any, List, Set, Union

import discord
from discord import app_commands
from discord.ext import commands, tasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from project_manager import project_manager, Project
import yaml
import safety
import admin_tools
from collections import deque
from safety_layer.sanitize import sanitize_outbound_text, sanitize_inbound_text, enforce_allowlist_mentions
from context.room_context import RoomContextBuilder, prepare_message_for_context
from prompt_loader import build_system_prompt as compose_system_prompt

# Add project to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from database import (
    init_db, ProfileRepository, MoodRepository, MemoryRepository,
    MoodLog, UserProfile, MessageRepository, MessageEvent
)
# Junk Modules Removed (Zoe V3 Reset)
from cadence_engine import CadenceEngine
# from game_server_manager import GameServerManager
# from vision_module import VisionModule
# from voice_module import VoiceModule
# from vector_store import get_memory_store

# Global Tool Managers (Simplified)
game_manager = None 
vision_module = None
voice_module = None
memory_store = None
poly_trader = None # Polymarket Trader

# Creative Pipeline Removed
creative_pipeline_started = False

import time
from database import ProfileRepository

# --- RECONSTRUCTED CONFIG ---
try:
    with open("config.yaml", "r") as f:
        ZOECONFIG = yaml.safe_load(f)
except FileNotFoundError:
    print("⚠️ config.yaml NOT found. Using defaults.")
    ZOECONFIG = {
        "discord": {"allowed_chat_channel_ids": [], "thoughts_channel_id": None, "admin_channel_ids": []},
        "admin": {"admin_user_ids": ["292890243852664855"]},
        "persona": {"mention_allowlist": []},
        "model": {"runtime_default": "gemini-2.5-flash-lite"}
    }

class BotConfig:
    def __init__(self, cfg):
        model_cfg = cfg.get("model", {})
        self.model = model_cfg.get("runtime_default", "gemini-2.5-flash-lite")
        self.escalation_model = model_cfg.get("escalation_model", "gemini-2.5-pro")
        self.allowed_providers = model_cfg.get("allowed_providers", ["gemini"])
        # Enforce Gemini-only at config level
        if "gemini" not in self.model.lower():
            print(f"WARNING: runtime_default '{self.model}' is not a Gemini model. Forcing gemini-2.5-flash-lite.")
            self.model = "gemini-2.5-flash-lite"

bot_config = BotConfig(ZOECONFIG)

# Initialize Cadence Engine with idle config from config.yaml
cadence_engine = CadenceEngine(idle_config=ZOECONFIG.get("idle", {}))

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
OWNER_DISCORD_USER_ID = int(os.getenv("OWNER_DISCORD_USER_ID", "292890243852664855"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
client = bot  # Alias
tree = bot.tree

# Global States
SESSION_ENGAGED_CHANNELS = set()
USER_MAP = {}
ROOM_BUFFERS = {} # channel_id -> deque of last 50 messages

# Import singleton instances
from thought_logger import thought_logger
from market_data import market_data
from paper_broker import paper_broker
from trading_engine_v4 import engine as TRADING_ENGINE
from model_router import model_router
from approval_gate import ApprovalGate
from game_server_manager import GameServerManager


# Load User Map
try:
    profiles = ProfileRepository.get_all()
    for p in profiles:
        for d_id in p.discord_ids:
            USER_MAP[str(d_id)] = p.profile_id
except Exception as e:
    print(f"⚠️ Failed to load USER_MAP: {e}")

# System prompt is now composed from /prompts/ files via prompt_loader.py
# The old inline build_system_prompt has been replaced.
# See: prompt_loader.build_system_prompt (imported as compose_system_prompt)


# ============================================================================
# Event Handlers
# ============================================================================

@bot.event
async def on_ready():
    print(f"🤖 {bot.user} is online!")
    print(f"   Guilds: {[g.name for g in bot.guilds]}")
    
    # Initialize Live Log
    thought_logger.log("system", "Clawdbot is starting up...", {"version": "1.2.0"})
    
    # Initialize database
    init_db()
    
    # Initialize Approval Gate
    global approval_gate
    approval_gate = ApprovalGate(bot)
    print("   🛡️ Approval Gate active (Rule: CHICKENSCRAPS)")
    
    # Initialize Game Manager
    print("   🎮 Game Manager ready")
    
    # Initialize Engagement Engine
    global engagement_engine
    engagement_engine = EngagementEngine(bot)
    print("   🎨 Engagement Engine ready")
    global game_manager
    game_manager = GameServerManager(approval_gate)
    print("   🎮 Game Manager active")
    
    # Initialize Vision
    global vision_module
    try:
        vision_module = VisionModule()
        print("   👁️ Vision Module active")
    except Exception as e:
        print(f"   ⚠️ Vision init failed: {e}")

    # Initialize Vector Memory Store
    global memory_store
    try:
        memory_store = get_memory_store()
        stats = memory_store.get_stats()
        print(f"   🧠 Memory Store active ({stats.get('points_count', 0)} vectors)")
    except Exception as e:
        print(f"   ⚠️ Memory Store init failed: {e}")

    # Load voice cog for voice channel integration
    try:
        from voice_worker import VoiceCog
        await client.add_cog(VoiceCog(client))
        print("   ✅ Voice cog loaded")
    except ImportError:
        pass
    except Exception as e:
        print(f"   ❌ Voice cog error: {e}")

    print(f"✅ Logged in as {client.user} (ID: {client.user.id})")
    print(f"🚀 Zoe V4 is active on {len(client.guilds)} servers.")
    
    # Start Trading Engine
    TRADING_ENGINE.start()
    
    
    # Sync slash commands
    try:
        synced = await tree.sync()
        print(f"✨ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    
    # Scheduler Jobs (Legacy Removed)
    # scheduler.add_job(morning_brief, ...)
    # scheduler.add_job(night_shift, ...)
    # scheduler.add_job(novelty_check, ...)
    # scheduler.add_job(boredom_check, ...)
    # scheduler.add_job(run_project_cycle, ...)
    
    # Only keep critical maintenance if needed (None for now)
    # scheduler.start() 
    print(f"   ⏰ APScheduler: No active jobs (Clean Reset)")
    
    # Watchdog active

    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        
        class HotReloadHandler(FileSystemEventHandler):
            def on_modified(self, event):
                if event.src_path.endswith('.py'):
                    print(f"🔄 Hot reload triggered by: {event.src_path}")
                    # Signal for restart
                    import sys
                    sys.exit(42)  # Exit code 42 = hot reload
        
        observer = Observer()
        observer.schedule(HotReloadHandler(), PROJECT_ROOT, recursive=False)
        observer.start()
        print("   👁️ Watchdog active (hot-reload enabled)")
    except Exception as e:
        print(f"   ⚠️ Watchdog not loaded: {e}")

    # Initialize Welcome Protocol
    try:
        from welcome_protocol import setup_welcome_protocol
        setup_welcome_protocol(bot)
        print("   👁️ Nosey Welcome Protocol active")
    except Exception as e:
        print(f"   ⚠️ Welcome Protocol failed: {e}")


@bot.event
async def on_message(message: discord.Message):
    """Handle incoming messages with strict logic."""
    channel_id = message.channel.id
    user_id = str(message.author.id)

    # --- ROOM CONTEXT MAINTENANCE ---
    if channel_id not in ROOM_BUFFERS:
        ROOM_BUFFERS[channel_id] = deque(maxlen=50)
        try:
            async for old_msg in message.channel.history(limit=20, oldest_first=True):
                if old_msg.author.bot and old_msg.author != bot.user: continue
                role = "admin" if str(old_msg.author.id) in [str(u) for u in ZOECONFIG.get("admin", {}).get("admin_user_ids", [])] else "user"
                record = prepare_message_for_context(old_msg.author.name, role, old_msg.content)
                ROOM_BUFFERS[channel_id].append(record)
        except:
            pass
    
    # Add current message
    role = "admin" if str(message.author.id) in [str(u) for u in ZOECONFIG.get("admin", {}).get("admin_user_ids", [])] else "user"
    record = prepare_message_for_context(message.author.name, role, message.content)
    ROOM_BUFFERS[channel_id].append(record)

    # 0. Basic Ignore (Self, Bots)
    if message.author.bot or message.author == bot.user:
        return

    # --- CONFIG LOADING (DYNAMIC) ---
    cfg = ZOECONFIG.get("discord", {})
    admin_cfg = ZOECONFIG.get("admin", {})
    
    ALLOWED_CHANNELS = cfg.get("allowed_chat_channel_ids", [])
    ADMIN_CHANNELS = cfg.get("admin_channel_ids", [])
    ADMIN_USER_IDS = [str(uid) for uid in admin_cfg.get("admin_user_ids", [])]
    
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_admin = user_id in ADMIN_USER_IDS
    # Admin Context: Is Admin AND (Is Admin Channel or DM)
    is_admin_context = is_admin and (channel_id in ADMIN_CHANNELS or is_dm)

    content = message.content.strip()
    content_lower = content.lower()

    # --- 1. ADMIN COMMAND ROUTING ---
    # Strict Prefix: !zoe or /zoe (if slash not caught)
    if content_lower.startswith("!zoe ") or content_lower.startswith("/zoe "):
        if not is_admin:
            await message.channel.send("Nice try. Ask Josh.")
            return
        
        # Parse Command
        parts = content.split()
        if len(parts) < 2: 
            return
        cmd = parts[1]
        args = parts[2:]
        
        # Execute via Admin Tools
        result = admin_tools.execute_admin_command(bot, cmd, args, int(user_id), channel_id, is_admin_context)
        await message.channel.send(result)
        return

    # --- 2. INTENT DETECTION (Direct Answers) ---
    # Fast path for specific questions
    if "what model" in content_lower:
         model_name = ZOECONFIG.get("model", {}).get("runtime_default", "Unknown Model")
         await message.channel.send(f"Running on: {model_name}")
         return

    if "alive" in content_lower and "?" in content_lower:
         await message.channel.send("I'm online. What's up?")
         return

    # --- 3. SHOULD RESPOND ROUTER ---
    should_reply = False
    
    # A) 100% Triggers (Mention, DM, Wake Word, Direct Reply)
    is_mentioned = bot.user in message.mentions
    is_reply_to_me = (message.reference and message.reference.resolved and 
                      message.reference.resolved.author == bot.user)
    wake_words = ["zoe", "hey zoe", "yo zoe", "hi zoe"]
    has_wake_word = any(w in content_lower for w in wake_words)

    if is_mentioned or is_dm or is_reply_to_me or has_wake_word:
        should_reply = True

    # B) 70% Probability (Short messages in allowed channels)
    elif channel_id in ALLOWED_CHANNELS and cfg.get("respond_without_tag", True):
        # Filter junk: Emoji only, "lol", code blocks
        if len(content) < 140 and not content.startswith("```"):
             # Valid textual message
             # Check Cooldown
             import time
             import random
             
             if not hasattr(bot, "last_public_response"): bot.last_public_response = 0
             
             cooldown = cfg.get("cooldown_seconds", 10)
             jitter = cfg.get("cooldown_jitter_seconds", 5)
             actual_wait = cooldown + random.uniform(0, jitter)
             
             if time.time() - bot.last_public_response > actual_wait:
                 # Roll dice: 70% chance
                 if random.random() < 0.7:
                     should_reply = True  

    # --- 4. EXECUTE RESPONSE ---
    if should_reply:
         # Update Last Response Time
         import time
         bot.last_public_response = time.time()
         
         # Cadence Activity Update
         cadence_engine.update_activity("ZOE")
         
         # Vision Check
         visual_context = ""
         if message.attachments:
             # Fast image check
             img = next((a for a in message.attachments if a.content_type and a.content_type.startswith("image/")), None)
             if img:
                 await message.add_reaction("👁️")
                 # Async vision call (fire and forget logic inside generation)
                 # For now passing blank or placeholder if strict speed needed
                 visual_context = f"[User uploaded image: {img.url}]"

         # Generate
         await generate_and_respond(message, visual_context, is_admin_context)


    # Persist message to DB
    profile_id = USER_MAP.get(str(message.author.id))
    msg_event = MessageEvent(
        id=str(uuid.uuid4()),
        source="discord",
        channel_id=str(message.channel.id),
        user_id=str(message.author.id),
        content=message.content,
        timestamp=datetime.now().isoformat(),
        profile_id=profile_id,
        discord_message_id=str(message.id),
        guild_id=str(message.guild.id) if message.guild else None
    )
    MessageRepository.insert(msg_event)

# ============================================================================
# Engagement Engine (Gifs & Screenshots)
# ============================================================================

class EngagementEngine:
    """Orchestrates beauty-posts: screenshots, GIFs, and captions."""
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = int(os.getenv("DISCORD_TRADES_CHANNEL_ID", "1462568915195527273"))
        
    async def post_trade_event(self, event_type: str, trade_id: str, symbol: str, details: Dict[str, Any]):
        """Post a high-end trade announcement."""
        channel = self.bot.get_channel(self.channel_id)
        if not channel: return

        # 1. Generate Caption & GIF
        from media_utils import CaptionGenerator, gif_picker
        caption = CaptionGenerator.get_caption(event_type)
        gif_url = await gif_picker.get_gif(event_type)

        # 2. Render Screenshot
        from renderer import renderer
        png_bytes = await renderer.render(kind="trade", target_id=trade_id)
        
        # 3. Upload Artifact & Get URL
        public_url = None
        if png_bytes:
            filename = f"trade_{trade_id}_{int(time.time())}.png"
            public_url = await renderer.upload_to_supabase(png_bytes, filename)
            
            # Record in artifacts table
            from supabase_memory import supabase_memory
            supabase_memory.add_artifact(
                artifact_id=str(uuid.uuid4()),
                instance_id="primary-v4-live",
                kind="trade_ticket",
                related_id=trade_id,
                url=public_url,
                metadata={"symbol": symbol, "event": event_type, **details}
            )

        # 4. Create Embed
        embed = discord.Embed(
            title=f"PAPER TRADE {event_type.split('_')[1]}ED: {symbol}",
            description=caption,
            color=0x00ff00 if "GREEN" in event_type or "OPEN" in event_type else 0xff0000,
            timestamp=datetime.now()
        )
        
        # Add Fields
        for k, v in details.items():
            embed.add_field(name=k.upper(), value=str(v), inline=True)
            
        embed.set_footer(text=f"Instance: primary-v4-live | Trade ID: {trade_id}")
        
        files = []
        if png_bytes:
            from io import BytesIO
            img_file = discord.File(BytesIO(png_bytes), filename="trade_ticket.png")
            embed.set_image(url="attachment://trade_ticket.png")
            files.append(img_file)
            
        # 5. Post
        await channel.send(embed=embed, files=files)
        
        # Optional: Post GIF separately if enabled
        if gif_url and os.getenv("GIFS_ENABLED", "true").lower() == "true":
             await channel.send(gif_url)

engagement_engine: Optional[EngagementEngine] = None


# ============================================================================
# Core Logic
# ============================================================================

OWNER_DISCORD_USER_ID = int(os.getenv("OWNER_DISCORD_USER_ID", "292890243852664855"))

def is_owner_dm(message: discord.Message) -> bool:
    """Check if message is a DM from the Owner."""
    # Ensure it's a DM (no guild) and author matches Owner ID
    return message.guild is None and message.author.id == OWNER_DISCORD_USER_ID

async def log_mood_signal(message: discord.Message):
    """Log mood signal from message."""
    try:
        user_id = str(message.author.id)
        profile_id = USER_MAP.get(user_id)
        if not profile_id:
            return

        # Simple sentiment analysis (Mock)
        # In real version, we'd use NLTK or TextBlob or LLM analysis
        # For now, just logging interaction
        MoodRepository.log_interaction(profile_id, "user_message", message.content)
        
    except Exception as e:
        print(f"⚠️ Mood Log Error: {e}")

async def generate_and_respond(message: discord.Message, visual_context: str = "", is_admin_channel: bool = False):
    """
    Cognitive Loop: Recall -> Context -> Compose Prompt -> LLM -> Sanitize -> Send.
    Uses file-based prompt composition from /prompts/.
    """
    from model_router import model_router
    from goal_engine import goal_engine

    user_id = str(message.author.id)
    profile_id = USER_MAP.get(user_id)

    # 1. PERMISSION CHECK (console only, never leaked)
    has_tools = is_admin_channel

    # 2. RECALL & CONTEXT
    profile = ProfileRepository.get(profile_id) if profile_id else None
    mood_trend = MoodRepository.get_trend(profile_id) if profile_id else {}
    memories = MemoryRepository.get_by_profile(profile_id, limit=5) if profile_id else []

    # Clean message content
    content = message.content.replace(f"<@{bot.user.id}>", "").strip()
    if visual_context:
        content += f"\n{visual_context}"

    # Semantic search for relevant memories
    semantic_memories = []
    if memory_store and memory_store.initialized:
        try:
            semantic_results = memory_store.search(content, profile_id=profile_id, limit=3)
            semantic_memories = [r['content'] for r in semantic_results]
        except Exception as e:
            print(f"Semantic search failed: {e}")

    # 3. BUILD ROOM_CONTEXT
    buffer = ROOM_BUFFERS.get(message.channel.id, [])
    msg_list = list(buffer)
    room_ctx_json = RoomContextBuilder.build(
        channel_id=message.channel.id,
        guild_id=message.guild.id if message.guild else None,
        messages=msg_list
    )

    # 4. STARTUP RITUAL CHECK
    is_startup = str(message.channel.id) not in SESSION_ENGAGED_CHANNELS
    if is_startup:
        SESSION_ENGAGED_CHANNELS.add(str(message.channel.id))

    # 5. COMPOSE SYSTEM PROMPT (from /prompts/ files)
    try:
        active_goals = goal_engine.get_current_obsessions()
    except Exception:
        active_goals = ""

    try:
        system_prompt = compose_system_prompt(
            config=ZOECONFIG,
            room_context_json=room_ctx_json,
            goals=active_goals,
            memories=semantic_memories,
            is_startup=is_startup,
            user_id=user_id,
        )
    except Exception as e:
        print(f"Prompt composition error: {e}")
        return

    # 6. CALL LLM
    async with message.channel.typing():
        try:
            user_content = f"CURRENT MESSAGE:\n{content}"
            messages = [{'role': 'user', 'content': user_content}]

            raw_response_text = await model_router.chat(
                messages=messages,
                system=system_prompt,
                model=bot_config.model
            )

            # 7. SANITIZE (single pass through consolidated sanitizer)
            if raw_response_text:
                cleaned = sanitize_outbound_text(raw_response_text)
                cleaned = enforce_allowlist_mentions(
                    cleaned,
                    ZOECONFIG.get("persona", {}).get("mention_allowlist", [])
                )

                if cleaned:
                    await message.channel.send(cleaned)
                    ROOM_BUFFERS[message.channel.id].append(
                        prepare_message_for_context("Zoe", "assistant", cleaned)
                    )

            # 8. LOG MOOD
            try:
                if hasattr(MoodRepository, 'log_interaction'):
                    await log_mood_signal(message)
            except Exception:
                pass

        except Exception as e:
            print(f"Generation error: {e}")
            await message.channel.send("brain glitch. give me a sec.")


# ============================================================================
# Slash Commands
# ============================================================================

@bot.tree.command(name="quote", description="Get real-time price from Polygon")
async def cmd_quote(interaction: discord.Interaction, symbol: str):
    await interaction.response.defer()
    price = market_data.get_price(symbol.upper())
    if price > 0:
        await interaction.followup.send(f"📈 **{symbol.upper()}**: ${price:.2f} (Source: Polygon)")
    else:
        await interaction.followup.send(f"⚠️ Could not fetch quote for {symbol.upper()}. Check API Key or Symbol.")

@bot.tree.command(name="pnl", description="Check Paper Account P&L")
async def cmd_pnl(interaction: discord.Interaction):
    await interaction.response.defer()
    
    user_id = str(interaction.user.id)
    summary = paper_broker.get_account_summary(user_id)
    
    pnl = summary.get("pnl", 0.0)
    equity = summary.get("equity", 100000.0)
    count = summary.get("open_count", 0)
    
    emoji = "📈" if pnl >= 0 else "📉"
    color_str = "+$" if pnl >= 0 else "-$"
    
    await interaction.followup.send(
        f"📊 **Paper Account Status** (Virtual $100k)\n"
        f"• Equity: ${equity:,.2f}\n"
        f"• P&L: {emoji} {color_str}{abs(pnl):,.2f}\n"
        f"• Open Positions: {count}"
    )

@bot.tree.command(name="scan", description="Scan for trade setups")
async def cmd_scan(interaction: discord.Interaction, symbols: str = "SPY,QQQ,IWM"):
    await interaction.response.defer()
    symbol_list = [s.strip().upper() for s in symbols.split(',')]
    
    try:
        candidates = trade_engine.scan(symbol_list)
        if not candidates:
            await interaction.followup.send("🔍 Scan complete. No high-quality setups found.")
            return

        msg = "**🔍 Scan Results:**\n"
        thought_msg = "**🧠 Zoe's Market Thoughts:**\n"
        
        for c in candidates:
            legs_str = ", ".join([f"{l.get('type')} {l.get('strike')}" for l in c['legs']])
            line = f"**{c['symbol']}** ({c['strategy']}) - Score: {c['score']}\nReason: {c['reason']}\nLegs: {legs_str}\n\n"
            msg += line
            thought_msg += line
        
        await interaction.followup.send(msg[:2000]) # Discord limit safely
        
        # Post to #zoe-thoughts
        await post_thought(interaction.guild, thought_msg)

    except Exception as e:
        await interaction.followup.send(f"⚠️ Scan failed: {e}")

@bot.tree.command(name="generate_plan", description="Generate today's trade gameplan (Draft)")
async def cmd_generate_plan(interaction: discord.Interaction):
    await interaction.response.defer()
    
    try:
        from model_router import model_router
        from supabase_memory import supabase_memory
        
        if not supabase_memory.initialized:
            await interaction.followup.send("❌ Database connection not ready.")
            return

        # 1. Ask Zoe to generate the plan
        prompt = """
        Generate a professional trading gameplan for today in JSON format.
        Focus on 3-4 high-liquidity symbols (SPY, QQQ, NVDA, TSLA).
        Return a JSON object with:
        {
          "regime": "string description",
          "items": [
            {
              "symbol": "string",
              "catalyst": "string summary",
              "regime": "string",
              "notes": "technical snapshot",
              "strategy": "string",
              "risk": "Tier 1 or Tier 2"
            }
          ]
        }
        Be ruthless and efficient in your analysis. Paper trade only.
        """
        
        raw_plan = await model_router.chat(
            messages=[{"role": "user", "content": prompt}],
            system="You are Zoe V4, a specialized options trading intelligence. Output ONLY raw JSON.",
            model="gemini-2.0-flash-lite"
        )
        
        # Clean JSON (in case of markdown blocks)
        cleaned_json = raw_plan.strip().replace("```json", "").replace("```", "").strip()
        plan_data = json.loads(cleaned_json)
        
        # 2. Persist to DB
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Create Gameplan record
        plan_insert = supabase_memory.client.table("daily_gameplans").upsert({
            "date": today,
            "status": "draft",
            "instance_id": "default"
        }).execute()
        
        if not plan_insert.data:
            await interaction.followup.send("❌ Failed to create gameplan record.")
            return
            
        plan_id = plan_insert.data[0]['id']
        
        # Delete old items if re-generating for the same day
        supabase_memory.client.table("daily_gameplan_items").delete().eq("plan_id", plan_id).execute()
        
        # Insert Items
        items_to_insert = []
        for item in plan_data.get("items", []):
            items_to_insert.append({
                "plan_id": plan_id,
                "symbol": item.get("symbol"),
                "catalyst_summary": item.get("catalyst"),
                "regime": item.get("regime"),
                "ivr_tech_snapshot": item.get("notes"),
                "preferred_strategy": item.get("strategy"),
                "risk_tier": item.get("risk")
            })
            
        supabase_memory.client.table("daily_gameplan_items").insert(items_to_insert).execute()
        
        await interaction.followup.send(f"✅ **Daily Gameplan Generated (Draft)**\nRegime: {plan_data.get('regime')}\nItems: {len(items_to_insert)}\nView it in the Zoe Terminal.")

    except Exception as e:
        await interaction.followup.send(f"❌ Failed to generate gameplan: {e}")

@bot.tree.command(name="positions", description="Show open paper positions")
async def cmd_positions(interaction: discord.Interaction):
    await interaction.response.defer()
    
    user_id = str(interaction.user.id)
    positions = paper_broker.get_positions(user_id)
    
    if not positions:
        await interaction.followup.send("No open positions found.")
        return
        
    msg = "**Open Positions:**\n"
    for p in positions:
        pnl = p.get('pnl_open', 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        msg += f"{emoji} **{p['symbol']}** {p['direction'].upper()} {p['quantity']}x @ ${p['entry_price']:.2f} | PnL: ${pnl:.2f}\n"
    
    await interaction.followup.send(msg[:2000])

async def post_thought(guild: discord.Guild, content: str):
    """Post to #zoe-thoughts channel."""
    if not guild: return
    channel = discord.utils.get(guild.text_channels, name="zoe-thoughts")
    if channel:
        try:
            await channel.send(content[:2000])
        except Exception as e:
            print(f"⚠️ Failed to post thought: {e}")

@bot.tree.command(name="me", description="Show your profile summary")
async def cmd_me(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    profile_id = USER_MAP.get(user_id)
    
    if not profile_id:
        await interaction.response.send_message("I don't have a profile for you yet. Talk more!", ephemeral=True)
        return
    
    profile = ProfileRepository.get(profile_id)
    if not profile:
        await interaction.response.send_message("Profile not found.", ephemeral=True)
        return
    
    interests = ", ".join(profile.interests.get("primary", [])[:3])
    inside_jokes = ", ".join(profile.interests.get("inside_jokes", [])[:2])
    phrases = ", ".join(profile.fingerprint.get("common_phrases", [])[:2])
    
    embed = discord.Embed(
        title=f"📋 {profile_id.capitalize()}'s Profile",
        color=discord.Color.blue()
    )
    embed.add_field(name="Style", value=profile.communication_style.get("style", "casual"), inline=True)
    embed.add_field(name="Humor", value=", ".join(profile.communication_style.get("humor_type", [])), inline=True)
    embed.add_field(name="Interests", value=interests or "Unknown", inline=False)
    embed.add_field(name="Inside Jokes", value=inside_jokes or "None captured", inline=False)
    embed.add_field(name="Catchphrases", value=phrases or "None", inline=False)
    
    await interaction.response.send_message(embed=embed)


# Legacy Commands Removed (Zoe V3 Reset)
# /tone, /mode, /projects, /mood, /transparency -> GONE.

@bot.tree.command(name="ping", description="Check if Zoe is online")
async def cmd_ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong. I'm here.", ephemeral=True)


@bot.tree.command(name="approve", description="Admin Only: Approve a pending action")
async def cmd_approve(interaction: discord.Interaction, request_id: str):
    # Check if user is CHICKENSCRAPS (292890243852664855)
    # TODO: Use constant
    if interaction.user.id != 292890243852664855:
        await interaction.response.send_message("🚫 You are not CHICKENSCRAPS.", ephemeral=True)
        return
    
@bot.tree.command(name="join_vc", description="Tell Zoe to join your voice channel")
async def cmd_join_vc(interaction: discord.Interaction):
    """Join the user's voice channel."""
    await interaction.response.defer(ephemeral=True)
    
    if not interaction.user.voice:
        await interaction.followup.send("❌ You aren't in a voice channel.", ephemeral=True)
        return
        
    channel = interaction.user.voice.channel
    
    try:
        # Disconnect if already connected elsewhere
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            
        vc = await channel.connect()
        await interaction.followup.send(f"🎧 Joined **{channel.name}**. I'm listening.", ephemeral=True)
        
        # Say hello
        audio_path = await voice_module.generate_speech("I'm in. Can you hear me?")
        vc.play(discord.FFmpegPCMAudio(audio_path))
        
    except Exception as e:
        await interaction.followup.send(f"⚠️ Failed to join: {e}", ephemeral=True)

@bot.tree.command(name="speak", description="Force Zoe to say something in VC")
async def cmd_speak(interaction: discord.Interaction, text: str):
    """Make Zoe speak text."""
    await interaction.response.defer(ephemeral=False)
    
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        await interaction.followup.send("❌ I'm not in a voice channel. Use `/join_vc` first.")
        return
        
    try:
        audio_path = await voice_module.generate_speech(text)
        vc.play(discord.FFmpegPCMAudio(audio_path))
        await interaction.followup.send(f"🗣️ **Said:** {text}")
    except Exception as e:
        await interaction.followup.send(f"⚠️ Failed to speak: {e}")
        
    await interaction.response.send_message(f"✅ Approved request {request_id} (Simulated).", ephemeral=True)


@bot.tree.command(name="games", description="Manage game servers")
@app_commands.choices(action=[
    app_commands.Choice(name="List", value="list"),
    app_commands.Choice(name="Start", value="start"),
    app_commands.Choice(name="Stop", value="stop")
])
async def cmd_games(interaction: discord.Interaction, action: app_commands.Choice[str], server: Optional[str] = None):
    await interaction.response.defer(ephemeral=True)
    act = action.value
    if act == "list":
        msg = await game_manager.list_servers()
        await interaction.followup.send(msg, ephemeral=True)
    elif act == "start":
        if not server:
            await interaction.followup.send("❌ Specify server name.", ephemeral=True)
            return
        msg = await game_manager.start_server(server, interaction.user.id)
        await interaction.followup.send(msg, ephemeral=True)
    elif act == "stop":
        if not server:
            await interaction.followup.send("❌ Specify server name.", ephemeral=True)
            return
        msg = await game_manager.stop_server(server, interaction.user.id)
        await interaction.followup.send(msg, ephemeral=True)

@bot.tree.command(name="market", description="Paper trade on Polymarket")
@app_commands.choices(action=[
    app_commands.Choice(name="Search", value="search"),
    app_commands.Choice(name="Portfolio", value="portfolio"),
    app_commands.Choice(name="Buy Yes", value="buy_yes"),
    app_commands.Choice(name="Buy No", value="buy_no")
])
async def cmd_market(interaction: discord.Interaction, action: app_commands.Choice[str], query: Optional[str] = None, amount: Optional[float] = 100.0):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    profile_id = USER_MAP.get(user_id, "unknown")
    act = action.value
    
    if act == "search":
        if not query:
            await interaction.followup.send("❌ Provide a query.", ephemeral=True)
            return
        res = await poly_trader.search_markets(query)
        await interaction.followup.send(res, ephemeral=True)
    
    elif act == "portfolio":
        res = await poly_trader.get_portfolio(profile_id)
        await interaction.followup.send(res, ephemeral=True)
    
    elif act in ["buy_yes", "buy_no"]:
        if not query: # reusing query arg for market_id
            await interaction.followup.send("❌ Provide market ID (use search).", ephemeral=True)
            return
        side = "yes" if act == "buy_yes" else "no"
        res = await poly_trader.place_trade(profile_id, query, side, amount)
        await interaction.followup.send(res, ephemeral=True)

@bot.tree.command(name="research", description="Use Zoe's browser tools")
async def cmd_research(interaction: discord.Interaction, url: str):
    await interaction.response.defer(ephemeral=True)
    
    if url.startswith("http"):
        content = tool_maps.read_url(url)
        # Summarize with LLM if too long? For now just return start
        await interaction.followup.send(f"📄 **Content Sample**:\n```{content[:800]}```", ephemeral=True)
    else:
        # Search
        res = tool_maps.search_web(url)
        await interaction.followup.send(res, ephemeral=True)

@bot.tree.command(name="glance", description="Zoe takes a look at the world (Webcam)")
async def cmd_glance(interaction: discord.Interaction, prompt: str = "What do you see? Be brief and witty."):
    await interaction.response.defer(ephemeral=False) # Public response so we can show image
    
    if not vision_module:
        await interaction.followup.send("❌ My eyes are not working right now (Vision Module init failed).")
        return

    # Capture and analyze
    # This might take a few seconds
    try:
        image_path = vision_module.capture_image()
        if not image_path:
            await interaction.followup.send("❌ Couldn't open the camera. Is it connected?", ephemeral=True)
            return
            
        description = vision_module.analyze_image(image_path, prompt)
        
        # Send image + description
        file = discord.File(image_path, filename="glance.jpg")
        await interaction.followup.send(f"👁️ **I see...**\n{description}", file=file)
        
        # Cleanup
        try:
            os.remove(image_path)
        except:
            pass
            
    except Exception as e:
        await interaction.followup.send(f"⚠️ Vision error: {e}", ephemeral=True)

@bot.tree.command(name="remember", description="Trigger memory ingestion from recent chats")
async def cmd_remember(interaction: discord.Interaction, hours: int = 24):
    await interaction.response.defer(ephemeral=True)
    
    try:
        from memory_ingestion import ingest_recent_history
        result = await ingest_recent_history(hours=hours)
        await interaction.followup.send(f"🧠 **Memory Ingestion Complete**\n{result}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Ingestion failed: {e}", ephemeral=True)

@bot.tree.command(name="plan", description="Create and execute a multi-step plan for complex tasks")
async def cmd_plan(interaction: discord.Interaction, goal: str):
    """Multi-turn planning with ReAct pattern."""
    await interaction.response.defer(ephemeral=False)
    
    try:
        from task_planner import plan_and_execute, StepStatus
        
        # Show planning message
        await interaction.followup.send(f"🎯 **Goal**: {goal}\n📋 Decomposing into steps...")
        
        # Track progress
        progress_messages = []
        
        def on_progress(step):
            emoji = "✅" if step.status == StepStatus.COMPLETED else "❌"
            progress_messages.append(f"{emoji} {step.description}")
        
        # Execute plan
        plan = await plan_and_execute(goal, on_progress)
        
        # Build result message
        steps_summary = "\n".join(f"  {i+1}. [{s.tool}] {s.description}" for i, s in enumerate(plan.steps))
        
        result_msg = f"""📊 **Plan Execution: {plan.status.value.upper()}**

**Steps:**
{steps_summary}

**Progress:**
{chr(10).join(progress_messages)}

**Result:**
{plan.final_result[:1500] if plan.final_result else 'No output'}"""
        
        await interaction.channel.send(result_msg)
        
    except Exception as e:
        await interaction.followup.send(f"⚠️ Planning failed: {e}", ephemeral=True)

@bot.tree.command(name="analyze", description="Force Zoe to analyze a market topic with visual data")
async def cmd_analyze(interaction: discord.Interaction, topic: str):
    """Trigger the BrainBridge to analyze a topic."""
    await interaction.response.defer(ephemeral=False)
    
    try:
        from research.brain_bridge import brain
        result = await brain.analyze_topic(topic)
        
        if result:
            files = []
            if result.get("image_path") and os.path.exists(result["image_path"]):
                files.append(discord.File(result["image_path"]))
                
            await interaction.followup.send(result["text"], files=files)
            
            # Cleanup
            if files:
                try:
                    os.remove(result["image_path"])
                except:
                    pass
        else:
            await interaction.followup.send("❌ Analysis yielded no results.")
            
    except Exception as e:
        await interaction.followup.send(f"⚠️ process failed: {e}", ephemeral=True)


# ============================================================================
# Background Tasks
# ============================================================================

@tasks.loop(seconds=60)
async def proactive_check():
    """
    Idle self-talk loop.
    Posts to the configured idle/thoughts channel when the room has been quiet.
    Rate limited per config (default: 1 post per 30 minutes).
    """
    idle_cfg = ZOECONFIG.get("idle", {})
    if not idle_cfg.get("enabled", True):
        return

    nudge_data = await cadence_engine.get_nudge_data()

    if not nudge_data or "log" in nudge_data:
        return

    nudge_text = nudge_data.get("text", "")
    if not nudge_text:
        return

    # Sanitize the nudge text through the outbound filter
    nudge_text = sanitize_outbound_text(nudge_text)
    if not nudge_text:
        return

    # Post ONLY to the configured thoughts/idle channel
    thoughts_channel_id = ZOECONFIG.get("discord", {}).get("thoughts_channel_id")
    if not thoughts_channel_id:
        return

    channel = bot.get_channel(int(thoughts_channel_id))
    if not channel:
        return

    try:
        # Truncate to Discord limit
        if len(nudge_text) > 1800:
            nudge_text = nudge_text[:1797] + "..."

        await channel.send(nudge_text)
        thought_logger.log("idle_talk", nudge_text, {
            "channel": channel.name,
            "channel_id": str(channel.id),
        })
    except discord.Forbidden:
        thought_logger.log("error", "Idle post failed: no permissions", {"channel_id": str(thoughts_channel_id)})
    except Exception as e:
        thought_logger.log("error", f"Idle post failed: {e}", {})


@tasks.loop(hours=24)
async def daily_digest():
    """Generate and post daily digest at 9 PM (or 9 AM)."""
    # Simple check for time (e.g. 9 AM)
    now = datetime.now()
    if now.hour == 9 and now.minute < 30:
        stats = MessageRepository.get_stats_now()
        channel = bot.get_channel(GUILD_ID) # Main guild channel? or verify ID.
        # Actually GUILD_ID is guild ID, not channel. Need a channel ID.
        # Using TARGET_VOICE_CHANNEL's text channel or finding a general one.
        # For now, just print to console to simulate.
        print(f"☀️ Morning Brief: {stats['count']} messages in history.")
        # TODO: Post to a real channel
    pass


@tasks.loop(seconds=60)
async def update_dashboard_loop():
    """Update the trading dashboard JSON every minute."""
    try:
        from research.dashboard_generator import DashboardGenerator
        gen = DashboardGenerator()
        path = gen.update_file()
        # thought_logger.log("system", "Dashboard updated", {"path": path})
    except Exception as e:
        print(f"Error updating dashboard: {e}")

# Loop removed

@tasks.loop(hours=4)
async def news_refresh():
    """Refresh news cache periodically."""
    # await refresh_news_if_needed() # Not implemented yet
    pass


@bot.tree.command(name="project", description="Manage long-running projects")
@app_commands.choices(action=[
    app_commands.Choice(name="Create New", value="new"),
    app_commands.Choice(name="Status Report", value="status"),
    app_commands.Choice(name="List All", value="list"),
    app_commands.Choice(name="Plan Next Steps", value="plan"),
    app_commands.Choice(name="Resume Work", value="resume"),
])
@app_commands.describe(name="Project name (required for 'new/resume')")
async def cmd_project(interaction: discord.Interaction, action: str, name: Optional[str] = None):
    """
    Manage Zoe's autonomous projects.
    """
    user_id = str(interaction.user.id)
    
    # Permission Check: Only Owner can manage projects
    if user_id != str(OWNER_DISCORD_USER_ID):
        await interaction.response.send_message("Only Josh can run projects.", ephemeral=True)
        return

    if action == "new":
        if not name:
            await interaction.response.send_message("Please specify a project name.", ephemeral=True)
            return
        
        try:
            # Create scaffolding
            project = project_manager.create_project(name, "Goal TBD")
            await interaction.response.send_message(f"🚀 Project **{name}** initialized!\nPath: `{project.path}`")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)

    elif action == "list":
        projects = project_manager.list_projects()
        if not projects:
            await interaction.response.send_message("No active projects.", ephemeral=True)
        else:
            p_list = "\n".join([f"- {p}" for p in projects])
            await interaction.response.send_message(f"📂 **Active Projects**:\n{p_list}")

    elif action == "resume":
        if not name:
             await interaction.response.send_message("Which project?", ephemeral=True)
             return
        await interaction.response.send_message(f"▶️ Resuming work on **{name}** (Scheduler will pick it up).")

    elif action == "status":
        # Show details of specified project or all
        if name:
            proj = project_manager.load_project(name)
            if not proj:
                await interaction.response.send_message(f"Project '{name}' not found.", ephemeral=True)
                return
            
            # Simple status view
            status = proj.data.get("status", "unknown")
            last = proj.data.get("last_update", "never")
            await interaction.response.send_message(
                f"📊 **{proj.name}**\n"
                f"Status: {status}\n"
                f"Last Update: {last}\n"
                f"Goal: {proj.data.get('goal')}"
            )

    elif action == "resume":
        if not name:
             await interaction.response.send_message("Which project?", ephemeral=True)
             return
        await interaction.response.send_message(f"▶️ Resuming work on **{name}** (Scheduler will pick it up).")

    else:
        await interaction.response.send_message("Training wheel mode: Command not fully implemented.", ephemeral=True)


# ============================================================================
# GAME FACTORY COMMANDS
# ============================================================================

# Define command group explicitly
try:
    game_group = app_commands.Group(name="game", description="Zoe Game Factory")

    @game_group.command(name="new", description="Start a new game project")
    @app_commands.choices(genre=[
        app_commands.Choice(name="Platformer", value="platformer"),
        app_commands.Choice(name="Shooter", value="shooter"),
        app_commands.Choice(name="Runner", value="runner"),
        app_commands.Choice(name="Puzzle", value="puzzle"),
        app_commands.Choice(name="Roguelite", value="roguelite")
    ])
    async def cmd_game_new(interaction: discord.Interaction, name: str, genre: app_commands.Choice[str]):
        await interaction.response.defer()
        # Lazy import to avoid circular dependency
        from game_factory import game_factory
        from creative_pipeline import creative_pipeline
        
        msg = await game_factory.create_new_game(name, genre.value)
        
        # Update pipeline state if active
        if creative_pipeline:
            slug = name.lower().replace(" ", "-")
            creative_pipeline.active_game_slug = slug
            creative_pipeline._save_state() # PERSIST MANUAL CHANGE
            await creative_pipeline._post_thought(f"Activated Game Project: {name}")
        
        await interaction.followup.send(msg)

    @game_group.command(name="build", description="Run one work unit (20-40m task)")
    async def cmd_game_build(interaction: discord.Interaction):
        await interaction.response.defer()
        from game_factory import game_factory
        from creative_pipeline import creative_pipeline
        
        slug = creative_pipeline.active_game_slug if creative_pipeline else None
        if not slug:
            await interaction.followup.send("⚠️ No active game project. Start one with `/game new`.")
            return

        await interaction.followup.send(f"🔨 Starting work unit for `{slug}`... (Check Discord/Logs)")
        msg = await game_factory.run_work_unit(slug)
        await interaction.followup.send(msg)

    @game_group.command(name="status", description="Show current game status")
    async def cmd_game_status(interaction: discord.Interaction):
        from creative_pipeline import creative_pipeline
        slug = creative_pipeline.active_game_slug if creative_pipeline else "None"
        is_running = creative_pipeline.is_running if creative_pipeline else False
        await interaction.response.send_message(f"🏭 **Game Factory Status**\n• Active Project: **{slug}**\n• Pipeline Running: {is_running}")

    bot.tree.add_command(game_group)
except Exception as e:
    print(f"Failed to register /game commands: {e}")


# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    # --- SELF-HEALING: PURGE DUPLICATES ---
    import psutil
    import os
    
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Look for other python instances running clawdbot.py
            cmd = proc.info.get('cmdline')
            if cmd and 'python' in cmd[0].lower() and 'clawdbot.py' in " ".join(cmd):
                if proc.info['pid'] != current_pid:
                    print(f"🔧 [Self-Healer] Found stale instance (PID {proc.info['pid']}). Terminating...")
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    print("🚀 Starting Clawdbot...")
    
    # --- PROACTIVE AGENT: AUTO-LAUNCH ---
    import subprocess
    import sys
    try:
        print("📢 [Self-Healer] Launching Proactive Nudge Engine...")
        subprocess.Popen([sys.executable, "proactive_agent.py"])
    except Exception as e:
        print(f"⚠️ [Self-Healer] Failed to launch Proactive Agent: {e}")

    bot.run(TOKEN)
