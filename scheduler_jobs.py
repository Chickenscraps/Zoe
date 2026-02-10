"""
Scheduler Jobs for Zoe
Cron-like scheduled tasks for bio-rhythm simulation.
Based on AGI Architecture Upgrade research §3.2.
"""
import asyncio
from datetime import datetime
from typing import Optional
import discord

# ============================================================================
# Morning Brief (08:00 daily)
# ============================================================================

async def morning_brief(bot: discord.Client, channel_id: int):
    """
    Generate and post the morning briefing.
    Runs at 08:00 daily.
    """
    from news_fetcher import get_news_summary, refresh_news_if_needed
    
    # Refresh news first
    await refresh_news_if_needed()
    
    # Get channel
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"⚠️ Morning Brief: Channel {channel_id} not found")
        return
    
    # Build the brief
    news = get_news_summary() or "No news available."
    
    # Get weather (mock for now)
    weather = "☀️ Weather data unavailable (TODO: integrate Open-Meteo)"
    
    # Get message stats
    try:
        from database import MessageRepository
        stats = MessageRepository.get_stats_now()
        activity = f"📊 Yesterday: {stats.get('count', 0)} messages logged."
    except Exception:
        activity = "📊 Activity stats unavailable."
    
    embed = discord.Embed(
        title="☀️ Morning Brief",
        description=f"Good morning, team. Here's what's up.",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.add_field(name="📰 Headlines", value=news[:500], inline=False)
    embed.add_field(name="🌤️ Weather", value=weather, inline=True)
    embed.add_field(name="📈 Activity", value=activity, inline=True)
    embed.set_footer(text="Zoe | Daily Digest")
    
    await channel.send(embed=embed)
    print("☀️ Morning Brief posted.")

# ============================================================================
# Night Shift (02:00 daily)
# ============================================================================

async def night_shift(bot: discord.Client):
    """
    Deep work mode: Summarize logs, clean temp files.
    Runs at 02:00 daily.
    """
    import os
    import shutil
    from pathlib import Path
    
    print("🌙 Night Shift starting...")
    
    # Clean temp vision files
    temp_vision = Path(os.path.dirname(__file__)) / "temp_vision"
    if temp_vision.exists():
        for f in temp_vision.glob("*.jpg"):
            try:
                f.unlink()
            except Exception:
                pass
        print("   🧹 Cleaned temp_vision/")
    
    # Clean old TTS files
    import tempfile
    tts_dir = Path(tempfile.gettempdir()) / "clawdbot_tts"
    if tts_dir.exists():
        for f in tts_dir.glob("tts_*.mp3"):
            try:
                f.unlink()
            except Exception:
                pass
        print("   🧹 Cleaned TTS cache")
    
    # Summarize daily activity (future: use LLM to create summary)
    try:
        from database import MessageRepository
        from datetime import timedelta
        
        # Get today's messages for summarization
        # (In future, pass to LLM for narrative summary)
        stats = MessageRepository.get_stats_now()
        print(f"   📊 Daily stats: {stats}")
    except Exception as e:
        print(f"   ⚠️ Stats failed: {e}")
    
    print("🌙 Night Shift complete.")

# ============================================================================
# Novelty Check (Every 1h)
# ============================================================================

async def novelty_check(bot: discord.Client, channel_id: int):
    """
    Check for wild & relevant news to share proactively.
    Runs every hour.
    """
    from news_fetcher import get_wild_item
    from cadence_engine import CadenceEngine
    
    # Get cadence engine (need to check if we should post)
    cadence = CadenceEngine()
    
    # Check if we should post (respect quiet hours and recent activity)
    if not cadence.should_respond(is_mentioned=False, is_reply=False):
        return
    
    # Get a wild/relevant item
    item = get_wild_item()
    if not item:
        return
    
    channel = bot.get_channel(channel_id)
    if not channel:
        return
    
    # Post it casually
    title = item.get("title", "Something interesting...")
    link = item.get("link", "")
    
    messages = [
        f"yo, did you see this? {title} {link}",
        f"lmao check this out: {title} {link}",
        f"wild. {title} {link}",
        f"thought you'd want to know: {title} {link}"
    ]
    
    import random
    msg = random.choice(messages)
    
    await channel.send(msg)
    print(f"🎲 Novelty posted: {title[:50]}...")

# ============================================================================
# Boredom Check (Every 5 mins - internal work cycles)
# ============================================================================

async def boredom_check(bot: discord.Client, channel_id: int):
    """
    Check if Zoe is bored and trigger creative coding.
    Runs every 5 minutes for internal work cycles.
    Only announces externally when appropriate (anti-spam).
    """
    from boredom_engine import boredom_engine, generate_announcement, who_might_be_awake
    
    
    # Run the creative cycle (State Machine)
    result = await boredom_engine.run_cycle(bot)
    
    if result and result.get("message"):
        # We have something to say!
        channel = bot.get_channel(channel_id)
        if channel:
            msg = result["message"]
            if len(msg) > 1950:
                msg = msg[:1950] + "...\n[Message Truncated]"
            await channel.send(msg)
            print(f"📢 Zoe Announced: {result['message'][:50]}...")
    
    if result and result.get("internal_log"):
        print(f"💭 {result['internal_log']}")

        
        if not project:
            print("[internal] Project creation failed or skipped")
            return
        
        print(f"✨ [internal] Completed: {project['name']}")
        
        # Decide whether to announce externally
        if not boredom_engine.should_announce():
            return
        
        # External announcement
        channel = bot.get_channel(channel_id)
        if not channel:
            return
        
        announcement = generate_announcement(project)
        await channel.send(announcement)
        
        # Update creation timestamp
        from datetime import datetime
        boredom_engine.last_announcement = datetime.now()
