
import time
import os
import json
import secrets
from datetime import datetime, timedelta
import sys
import subprocess
import random
import threading

# Import Skill Modules
SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT PERSONA SKILL")
PROJECT_ROOT = os.path.abspath(os.path.join(SKILL_DIR, ".."))

if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)


try:
    from event_bus import notify_user, event_bus, Event, EventType
    from mood_engine import mood_engine, InternalMood
    from tts_engine import tts_engine
    from structured_logger import logger
    from news_watcher import news_watcher
    from discord_bridge import discord_bridge
    from nudge_engine import nudge_engine
except ImportError as e:
    print(f"Error importing skill modules: {e}")
    # Fallback dummies
    class MockObj:
        def __getattr__(self, name): return lambda *a, **k: None
    notify_user = lambda *a, **k: print(f"Notify: {a}")
    event_bus = mood_engine = tts_engine = logger = news_watcher = discord_bridge = nudge_engine = MockObj()
    EventType = MockObj()

# Configuration
CHECK_INTERVAL = 300  # 5 minute loop - less frequent updates while working
IDLE_THRESHOLD_MINUTES = 5

def is_idle():
    """Check if user is idle (no recent user messages)."""
    try:
        if hasattr(event_bus, 'get_recent_events'):
            history = event_bus.get_recent_events(50)
            now = datetime.now()
            for event in reversed(history):
                if event.type == "user_message":
                    # Parse timestamp (assuming ISO format in event.timestamp)
                    ts = datetime.fromisoformat(event.timestamp)
                    if (now - ts).total_seconds() < (IDLE_THRESHOLD_MINUTES * 60):
                        return False
    except Exception:
        pass
    return True


def speak(text):
    """Uses tts_engine for mood-aware speech."""
    try:
        from mood_engine import mood_engine
        modifiers = mood_engine.get_voice_modifiers()
        from tts_engine import tts_engine
        tts_engine.speak(text, mood_modifiers=modifiers)
    except:
        pass

def shout(message, nudge_type="general", urgency="normal", tags=None):
    """Reaches out to the user via Notification Router."""
    print(f"\n🔔 [Proactive Nudge]: {message}")
    
    logger.info("proactive.nudge", message, metadata={"type": nudge_type, "urgency": urgency})
    
    # Use Notification Router directly via event bus or function if available
    # Here we emulate the router's role via notify_user helper from event_bus
    notify_user(
        title=f"Clawd ({nudge_type})",
        message=message,
        urgency=urgency,
        source="proactive_agent"    
    )

def check_desktop_clutter():
    """ADHD Sweep: Check for messy desktop."""
    try:
        files = [f for f in os.listdir(DESKTOP_PATH) if os.path.isfile(os.path.join(DESKTOP_PATH, f))]
        count = len(files)
        
        # Mood check: If Irritated, lower threshold
        threshold = 15
        mood = mood_engine.get_current_mood()
        if mood == InternalMood.IRRITATED_MASKED:
            threshold = 10
            
        if count > threshold:
            msg = f"👀 I count {count} files on your desktop."
            if mood == InternalMood.IRRITATED_MASKED:
                msg += " It's getting a bit messy. Can we clean this up?"
            else:
                msg += " Want to do a quick 5-minute 'File Flurry'?"
            
            shout(msg, "clutter", urgency="normal")
            return True
            
    except Exception as e:
        logger.error("proactive.error", str(e), metadata={"check": "desktop"})
    return False

def check_stream_status():
    """Check if anyone is live in the Discord voice channel."""
    try:
        # Channel ID: 1174052382057963623
        status = discord_bridge.check_channel_status("1174052382057963623")
        
        # We need state to track if we already alerted
        state_file = os.path.join(SKILL_DIR, "state.json")
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
        except:
            state = {}

        was_live = state.get("stream_live_alerted", False)
        is_live = status.get("is_live", False)
        
        if is_live and not was_live:
            streamer = status.get("streamer_name", "Someone")
            shout(f"🔴 {streamer} is LIVE in Discord!", "stream_alert", urgency="high")
            state["stream_live_alerted"] = True
            with open(state_file, "w") as f:
                json.dump(state, f)
        elif not is_live and was_live:
            # Reset alert
            state["stream_live_alerted"] = False
            with open(state_file, "w") as f:
                json.dump(state, f)
                
    except Exception:
        pass

def check_news_pulse():
    """Tick the news watcher."""
    try:
        news_watcher.tick()
    except Exception:
        pass

def check_procrastination():
    """Vision-based procrastination check (stub for now)."""
    # Logic moved to vision_perceiver module, called here occasionally
    pass

def main():
    # Single Instance Lock
    LOCK_FILE = os.path.join(SKILL_DIR, "proactive.lock")
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            if os.path.exists(f"/proc/{pid}") or psutil_process_exists(pid):
                print(f"🚫 Proactive Agent already running (PID {pid}). Exiting.")
                return
            else:
                print("⚠️ Stale lock file found. Removing.")
                os.remove(LOCK_FILE)
    except Exception:
        pass
        
    # Create Lock
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
        
    # Register cleanup
    import atexit
    def cleanup_lock():
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    atexit.register(cleanup_lock)

    print("🚀 Proactive Agent Online. Modules Loaded.")
    logger.info("system.startup", "Proactive Agent started")
    
    # Send startup ping
    shout("I'm online. Watching news, streams, and your desktop.", "startup")
    
    mins_counter = 0
    
    while True:
        try:
            # 1. News Pulse (Internal jitter logic inside news_watcher)
            check_news_pulse()
            
            # 2. Stream Watch (Every minute)
            check_stream_status()
            
            # 3. Idle Work Loop (Every minute, but only acts if idle)
            if is_idle():
                # Nudge Engine handles rotation (Progress, Research, Review, etc.)
                # It will only post if significant or if specific ticks are chosen
                result = nudge_engine.tick()
                logger.info("proactive.nudge_tick", result)
                
            # 4. Maintenance / Mood Decay (Every 10 mins)
            if mins_counter % 10 == 0:
                mood_engine.decay_mood()
                
            mins_counter += 1
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error("proactive.loop_error", str(e))
            time.sleep(60)

def share_music():
    """Share a track based on user history and current mood."""
    try:
        profile_path = os.path.join(SKILL_DIR, "music_profile.json")
        if not os.path.exists(profile_path):
            return

        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        history = data.get("global_history", [])
        if not history:
            return
            
        # Pick a random track
        track = random.choice(history)
        user = track.get("user", "Someone")
        link_id = track.get("id")
        platform = track.get("platform")
        
        # Construct valid URL
        url = ""
        if platform == "spotify_track":
            url = f"https://open.spotify.com/track/{link_id}"
        elif platform == "spotify_album":
            url = f"https://open.spotify.com/album/{link_id}"
        elif platform == "youtube_video":
            url = f"https://www.youtube.com/watch?v={link_id}"
        elif platform == "soundcloud":
            url = f"https://soundcloud.com/{link_id}"
        elif platform == "apple_music":
            url = f"https://music.apple.com/us/album/{link_id}"
        else:
            return # Skip unknown platforms
        
        # Mood-based commentary
        mood = mood_engine.get_current_mood()
        
        comment = ""
        if mood == InternalMood.SUNNY_SOCIAL:
            comment = f"Remember when {user} dropped this banger? 🎵"
        elif mood == InternalMood.DEEP_THINKER:
            comment = f"Analyzing this track from {user}... classic."
        elif mood == InternalMood.SHARP_EXEC:
            comment = f"Focus fuel courtesy of {user}."
        elif mood == InternalMood.IRRITATED_MASKED:
            comment = f"Even I can appreciate this one from {user}."
        else:
            comment = f"Listening to some {user} history."
            
        full_msg = f"{comment}\n{url}"
        shout(full_msg, "music", urgency="low")
        
    except Exception as e:
        logger.error("proactive.music_error", str(e))

if __name__ == "__main__":
    main()
