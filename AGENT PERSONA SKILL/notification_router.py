"""
Notification Router for Clawdbot
Centralized router for all agent-initiated communication.
Integrates with event bus, Discord, TTS, and enforces budgets/quiet hours.
"""
import os
import json
import time
import winsound
import subprocess
import asyncio
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from win11toast import toast

# Optional imports
try:
    from journal import log_event
    JOURNAL_AVAILABLE = True
except ImportError:
    def log_event(*args, **kwargs): pass
    JOURNAL_AVAILABLE = False

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SKILL_DIR)
SETTINGS_FILE = os.path.join(SKILL_DIR, "settings.json")
NOTIFICATION_LOG = os.path.join(SKILL_DIR, "notification_history.jsonl")
NOTIFICATION_FEED = os.path.join(SKILL_DIR, "notification_feed.jsonl")

# Default chat URL
CHAT_URL = "http://localhost:18789/chat?session=agent%3Amain%3Amain"

# State
_recent_notifications: Dict[str, float] = {}
_hourly_count = 0
_hour_start = datetime.now()
_last_user_activity = 0.0

def load_settings() -> Dict:
    """Load settings from settings.json."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {
        "notifications": {
            "enabled": True,
            "quiet_hours": {"start": "22:00", "end": "08:00"},
            "max_toasts_per_hour": 6,
            "dedupe_window_seconds": 300,
            "in_flow_suppression": True,
            "in_flow_window_seconds": 300
        }
    }

def _get_notification_hash(title: str, message: str) -> str:
    """Generate hash for deduplication."""
    return hashlib.md5(f"{title}:{message}".encode()).hexdigest()

def _check_hourly_budget() -> bool:
    """Check and reset hourly notification budget."""
    global _hourly_count, _hour_start
    
    now = datetime.now()
    if now - _hour_start >= timedelta(hours=1):
        _hourly_count = 0
        _hour_start = now
    
    settings = load_settings()
    max_per_hour = settings.get("notifications", {}).get("max_toasts_per_hour", 6)
    
    return _hourly_count < max_per_hour

def _is_duplicate(title: str, message: str, window_seconds: int = 300) -> bool:
    """Check if this notification was recently sent."""
    global _recent_notifications
    
    now = time.time()
    notif_hash = _get_notification_hash(title, message)
    
    # Clean old entries
    _recent_notifications = {
        h: t for h, t in _recent_notifications.items()
        if now - t < window_seconds
    }
    
    if notif_hash in _recent_notifications:
        # Refresh timestamp on duplicate hit
        _recent_notifications[notif_hash] = now
        return True
    
    _recent_notifications[notif_hash] = now
    return False

def _is_in_flow() -> bool:
    """Check if user is currently 'in flow' (active recently)."""
    # This would ideally check system idle time or journal logs
    # For now, we utilize the _last_user_activity global updated by journal
    global _last_user_activity
    settings = load_settings()
    
    if not settings.get("notifications", {}).get("in_flow_suppression", True):
        return False
        
    window = settings.get("notifications", {}).get("in_flow_window_seconds", 300)
    
    # Check journal specifically for user inputs
    if JOURNAL_AVAILABLE:
        try:
            log_file = os.path.join(SKILL_DIR, "journal_normal.jsonl")
            if os.path.exists(log_file):
                # Read last few lines to find user input
                with open(log_file, "r") as f:
                    lines = f.readlines()[-20:]
                    for line in reversed(lines):
                        try:
                            entry = json.loads(line)
                            if entry.get("event") in ["user_message", "cli_command"]:
                                t_str = entry.get("timestamp")
                                if t_str:
                                    t = datetime.fromisoformat(t_str).timestamp()
                                    if time.time() - t < window:
                                        return True
                        except:
                            continue
        except Exception:
            pass
            
    return False

def is_quiet_hours(settings: Dict = None) -> bool:
    """Check if current time is within quiet hours."""
    if settings is None:
        settings = load_settings()
    
    config = settings.get("notifications", {}).get("quiet_hours", {"start": "22:00", "end": "08:00"})
    start = config.get("start", "22:00")
    end = config.get("end", "08:00")
    
    now = datetime.now().strftime("%H:%M")
    
    if start < end:
        return start <= now <= end
    else:  # Over midnight
        return now >= start or now <= end

def push_to_openclaw(message: str) -> bool:
    """Push message to OpenClaw gateway."""
    try:
        # Use simple POST to local CLI or gateway if possible
        # Falling back to subprocess for now
        subprocess.Popen(
            f'pnpm openclaw chat "{message}" --session "agent:main:main" --timeout 5000',
            cwd=PROJECT_ROOT,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        print(f"OpenClaw Push Error: {e}")
        return False

def _log_to_feed(message: str, notif_type: str = "general", importance: float = 0.5, link: str = None):
    """Log notification to the feed file."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "type": notif_type,
        "importance": importance,
        "link": link
    }
    with open(NOTIFICATION_FEED, "a") as f:
        f.write(json.dumps(entry) + "\n")

def play_chime(urgency: str = "normal"):
    """Play a chime based on urgency."""
    try:
        def _play():
            if urgency == "critical":
                # Urgent: Ascending major triad + octave
                for freq in [523, 659, 784, 1047]:
                    winsound.Beep(freq, 100)
                winsound.Beep(1047, 400)
            elif urgency == "high":
                # Important: Double high
                winsound.Beep(880, 100)
                time.sleep(0.05)
                winsound.Beep(880, 100)
            else:
                # Normal: Friendly "boop-beep"
                winsound.Beep(784, 80)
                time.sleep(0.05)
                winsound.Beep(1047, 100)
        
        threading.Thread(target=_play, daemon=True).start()
    except Exception:
        pass

def route_attention(
    title: str,
    message: str,
    urgency: str = "normal",
    action_url: str = None,
    speaks: bool = True,
    notify_discord: bool = False,
    source: str = "unknown",
    correlation_id: str = None,
    tags: List[str] = None,
    link: str = None
) -> bool:
    """
    Centralized router for all agent-initiated communication.
    
    Args:
        title: Notification title
        message: Notification message
        urgency: "low", "normal", "high", "critical"
        action_url: URL to open on click
        speaks: Whether to use TTS
        notify_discord: Also send to Discord
        source: Source module for logging
        correlation_id: For tracing
        tags: List of tags ["news", "clarify", "system"]
        link: Optional relevant link
    """
    global _hourly_count
    
    settings = load_settings()
    notif_settings = settings.get("notifications", {})
    
    # 1. Check enabled
    if not notif_settings.get("enabled", True) and urgency != "critical":
        return False
        
    # 2. Quiet Hours (critical bypasses)
    if is_quiet_hours(settings) and urgency not in ["critical", "high"]:
        _log_to_feed(f"[Quiet Hours] {title}: {message}", "suppressed")
        return False
        
    # 3. Budget Check (critical bypasses)
    if not _check_hourly_budget() and urgency != "critical":
        _log_to_feed(f"[Budget Limit] {title}: {message}", "suppressed")
        return False
        
    # 4. In-Flow Suppression (critical/high bypasses)
    if urgency not in ["critical", "high"] and _is_in_flow():
        _log_to_feed(f"[In-Flow] {title}: {message}", "suppressed")
        return False

    # 5. Deduplication
    dedupe_window = notif_settings.get("dedupe_window_seconds", 300)
    if _is_duplicate(title, message, dedupe_window) and urgency != "critical":
        return False
        
    # --- Passed Gates ---
    
    _hourly_count += 1
    
    # Log to feed
    _log_to_feed(f"{title}: {message}", "notification", 
                 importance=0.9 if urgency=="critical" else 0.5,
                 link=link)
    
    # Structured Log
    try:
        from structured_logger import logger
        logger.info("notification.sent", f"{title}: {message}",
                   source=source, correlation_id=correlation_id,
                   metadata={"urgency": urgency, "tags": tags})
    except ImportError:
        pass

    # Play Chime
    play_chime(urgency)
    
    # Show Toast
    try:
        on_click = action_url or link or CHAT_URL
        toast(title, message, on_click=on_click, duration='long')
    except Exception as e:
        print(f"Toast error: {e}")
        
    # Push to OpenClaw Chat
    push_to_openclaw(f"{title}: {message}")
    
    # Discord
    if notify_discord:
        try:
            from discord_bridge import send_message
            send_message(f"🔔 **{title}**: {message}")
        except ImportError:
            pass
            
    # TTS
    if speaks:
        try:
            from tts_engine import tts_engine
            # Get mood modifiers
            try:
                from mood_engine import mood_engine
                mods = mood_engine.get_voice_modifiers()
            except ImportError:
                mods = None
            
            tts_engine.speak(message, mood_modifiers=mods)
        except ImportError:
            # Fallback
            subprocess.Popen(f'powershell -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{message}\')"', shell=True)
            
    # Log to history
    entry = {
        "timestamp": datetime.now().isoformat(),
        "title": title,
        "message": message,
        "urgency": urgency,
        "source": source,
        "correlation_id": correlation_id,
        "tags": tags,
        "link": link
    }
    with open(NOTIFICATION_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
        
    return True

if __name__ == "__main__":
    print("Testing Notification Router...")
    route_attention(
        "Test Notification",
        "This is a test of the enhanced notification router.",
        urgency="normal",
        tags=["test"],
        link="https://google.com"
    )

import winsound
import subprocess
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from win11toast import toast

try:
    from journal import log_event
except ImportError:
    def log_event(*args, **kwargs): pass

try:
    import discord
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SKILL_DIR)
SETTINGS_FILE = os.path.join(SKILL_DIR, "settings.json")
NOTIFICATION_LOG = os.path.join(SKILL_DIR, "notification_history.jsonl")
NOTIFICATION_FEED = os.path.join(SKILL_DIR, "notification_feed.jsonl")

# Default chat URL - OpenClaw Gateway
CHAT_URL = "http://localhost:18789/chat?session=agent%3Amain%3Amain"

# Deduplication cache
_recent_notifications: Dict[str, float] = {}
_hourly_count = 0
_hour_start = datetime.now()

def _get_notification_hash(title: str, message: str) -> str:
    """Generate hash for deduplication."""
    return hashlib.md5(f"{title}:{message}".encode()).hexdigest()

def _check_hourly_budget() -> bool:
    """Check and reset hourly notification budget."""
    global _hourly_count, _hour_start
    
    now = datetime.now()
    if now - _hour_start >= timedelta(hours=1):
        _hourly_count = 0
        _hour_start = now
    
    settings = load_settings()
    max_per_hour = settings.get("notification_budget", {}).get("max_per_hour", 6)
    
    return _hourly_count < max_per_hour

def _is_duplicate(title: str, message: str, window_seconds: int = 120) -> bool:
    """Check if this notification was recently sent."""
    global _recent_notifications
    
    now = time.time()
    notif_hash = _get_notification_hash(title, message)
    
    # Clean old entries
    _recent_notifications = {
        h: t for h, t in _recent_notifications.items()
        if now - t < window_seconds
    }
    
    if notif_hash in _recent_notifications:
        return True
    
    _recent_notifications[notif_hash] = now
    return False

def push_to_openclaw(message: str) -> bool:
    """Push a message to the OpenClaw gateway using the CLI."""
    try:
        result = subprocess.run(
            f'pnpm openclaw chat "{message}" --session "agent:main:main" --timeout 5000',
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            shell=True
        )
        if result.returncode == 0:
            return True
        else:
            print(f"OpenClaw CLI failed: {result.stderr}")
            # Fallback: Log to notification feed
            _log_to_feed(message, "proactive")
    except Exception as e:
        print(f"OpenClaw Push Error: {e}")
    return False

def _log_to_feed(message: str, notif_type: str = "general"):
    """Log notification to the feed file."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "type": notif_type
    }
    with open(NOTIFICATION_FEED, "a") as f:
        f.write(json.dumps(entry) + "\n")

def push_to_discord(message: str, channel_id: str = None) -> bool:
    """Push a message to Discord using the Discord REST API."""
    if not DISCORD_AVAILABLE:
        print("Discord.py not installed. Install with: pip install discord.py")
        return False
    
    try:
        # Load Discord token from openclaw config
        config_path = os.path.expanduser("~/.openclaw/openclaw.json")
        with open(config_path, "r") as f:
            config = json.load(f)
            token = config.get("channels", {}).get("discord", {}).get("token")
        
        if not token:
            print("Discord token not found in openclaw.json")
            return False
        
        # Use default channel from config if not specified
        if not channel_id:
            settings = load_settings()
            channel_id = settings.get("discord", {}).get("default_channel", "1470130507118280856")
        
        # Send message using Discord REST API
        async def send_message():
            import aiohttp
            headers = {
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json"
            }
            payload = {"content": message}
            url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    return resp.status == 200
        
        # Run async function
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule it
                asyncio.create_task(send_message())
                return True
            else:
                return loop.run_until_complete(send_message())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(send_message())
            loop.close()
            return result
        
    except Exception as e:
        print(f"Discord Push Error: {e}")
        return False

def play_chime(urgency: str = "normal"):
    """Play Mr Gagger's signature chime - a unique musical pattern."""
    try:
        import threading
        def _play():
            if urgency == "critical":
                # Urgent: Dramatic ascending scale
                for freq in [523, 659, 784, 1047]:  # C5, E5, G5, C6 - major chord arpeggio
                    winsound.Beep(freq, 100)
                winsound.Beep(1047, 300)  # Hold the high note
            elif urgency == "high":
                # Important: Double chime
                winsound.Beep(880, 100)  # A5
                time.sleep(0.05)
                winsound.Beep(1047, 150)  # C6
                time.sleep(0.1)
                winsound.Beep(880, 100)  # A5
                winsound.Beep(1047, 150)  # C6
            else:
                # Normal: Mr Gagger's signature "boop-boop-beep" melody
                winsound.Beep(659, 80)   # E5
                time.sleep(0.02)
                winsound.Beep(784, 80)   # G5
                time.sleep(0.02)
                winsound.Beep(1047, 150) # C6 - the signature high "ding"
                time.sleep(0.05)
                winsound.Beep(988, 200)  # B5 - falling resolution
        
        # Play in background thread so it doesn't block
        threading.Thread(target=_play, daemon=True).start()
    except Exception:
        pass


def load_settings() -> Dict:
    """Load settings from settings.json."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {
        "quiet_hours": {"start": "22:00", "end": "08:00"},
        "snooze_duration": 300,
        "max_frequency": 60,
        "enabled": True,
        "notification_budget": {"max_per_hour": 6, "toast_enabled": True, "voice_enabled": True}
    }

def is_quiet_hours(settings: Dict = None) -> bool:
    """Check if current time is within quiet hours."""
    if settings is None:
        settings = load_settings()
    
    now = datetime.now().strftime("%H:%M")
    start = settings["quiet_hours"]["start"]
    end = settings["quiet_hours"]["end"]
    
    if start < end:
        return start <= now <= end
    else:  # Over midnight
        return now >= start or now <= end

def route_attention(
    title: str,
    message: str,
    urgency: str = "normal",
    action_url: str = None,
    speaks: bool = True,
    notify_discord: bool = False,
    source: str = "unknown",
    correlation_id: str = None
) -> bool:
    """
    Centralized router for any agent-initiated communication.
    Respects budgets, deduplication, and quiet hours.
    
    Args:
        title: Notification title
        message: Notification message
        urgency: "low", "normal", "high", "critical"
        action_url: URL to open on click (default: OpenClaw chat)
        speaks: Whether to use TTS
        notify_discord: Also send to Discord
        source: Source module for logging
        correlation_id: For tracing
    
    Returns:
        True if notification was sent, False if suppressed
    """
    global _hourly_count
    
    settings = load_settings()
    
    # Check if enabled
    if not settings.get("enabled", True) and urgency != "critical":
        return False
    
    # Quiet Hours Check (critical bypasses)
    if is_quiet_hours(settings) and urgency not in ["critical", "high"]:
        print(f"[NotificationRouter] Suppressed (quiet hours): {title}")
        _log_to_feed(f"[Suppressed - Quiet Hours] {title}: {message}", "suppressed")
        return False
    
    # Budget check (critical bypasses)
    if not _check_hourly_budget() and urgency != "critical":
        print(f"[NotificationRouter] Suppressed (budget): {title}")
        _log_to_feed(f"[Suppressed - Budget] {title}: {message}", "suppressed")
        return False
    
    # Deduplication check
    dedupe_window = settings.get("notification_budget", {}).get("dedupe_window_seconds", 120)
    if _is_duplicate(title, message, dedupe_window) and urgency != "critical":
        print(f"[NotificationRouter] Suppressed (duplicate): {title}")
        return False
    
    # Increment budget counter
    _hourly_count += 1
    
    # Log the attempt
    log_event("agent.attention", message, {
        "title": title,
        "urgency": urgency,
        "source": source,
        "correlation_id": correlation_id
    }, mode="organize")
    
    # Log to structured logger if available
    try:
        from structured_logger import logger
        logger.info("notification.sent", f"{title}: {message}", 
                   source=source, correlation_id=correlation_id,
                   metadata={"urgency": urgency})
    except ImportError:
        pass
    
    # Update metrics
    try:
        from server import metrics
        metrics.record_toast()
    except ImportError:
        pass
    
    # Play chime FIRST so user hears it
    if settings.get("notification_budget", {}).get("toast_enabled", True):
        play_chime(urgency)
    
    # Send Toast - clicking opens OpenClaw chat
    toast_enabled = settings.get("notification_budget", {}).get("toast_enabled", True)
    if toast_enabled:
        try:
            on_click = action_url if action_url else CHAT_URL
            toast(title, message, on_click=on_click, duration='long')
        except Exception as e:
            print(f"Toast Error: {e}")
    
    # Also push to OpenClaw chat so it appears in the session
    push_to_openclaw(f"{title}: {message}")
    
    # Discord notification if requested
    if notify_discord:
        push_to_discord(f"🔔 **{title}**: {message}")
    
    # Voice Output
    voice_enabled = settings.get("notification_budget", {}).get("voice_enabled", True)
    if speaks and voice_enabled:
        try:
            from tts_engine import tts_engine
            
            # Get mood modifiers if available
            try:
                from mood_engine import mood_engine
                mood_modifiers = mood_engine.get_voice_modifiers()
            except ImportError:
                mood_modifiers = None
            
            tts_engine.speak(message, mood_modifiers=mood_modifiers)
        except ImportError:
            # Fallback to dispatcher speak
            try:
                from dispatcher import speak
                speak(message)
            except ImportError:
                pass
    
    # Log to notification history
    _log_notification(title, message, urgency, source, correlation_id)
    
    return True

def _log_notification(title: str, message: str, urgency: str, source: str, correlation_id: str):
    """Log notification to history."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "title": title,
        "message": message,
        "urgency": urgency,
        "source": source,
        "correlation_id": correlation_id
    }
    try:
        with open(NOTIFICATION_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def handle_agent_wants_user(event):
    """
    Event handler for agent_wants_user events from the event bus.
    """
    payload = event.payload
    
    title = payload.get("title", "Agent Message")
    message = payload.get("message", "")
    urgency = payload.get("urgency", "normal")
    
    route_attention(
        title=title,
        message=message,
        urgency=urgency,
        source=event.source,
        correlation_id=event.correlation_id
    )

def setup_event_bus_subscription():
    """Subscribe to event bus for agent_wants_user events."""
    try:
        from event_bus import event_bus, EventType
        event_bus.subscribe(EventType.AGENT_WANTS_USER.value, handle_agent_wants_user)
        print("[NotificationRouter] Subscribed to event bus")
    except ImportError:
        print("[NotificationRouter] Event bus not available")

# Auto-subscribe on import
try:
    setup_event_bus_subscription()
except Exception:
    pass

if __name__ == "__main__":
    # Test
    print("Testing Notification Router...")
    
    # Test basic notification
    result = route_attention(
        "Mr Gagger Test",
        "Notification with chime, chat link, and budget tracking!",
        speaks=False,
        notify_discord=False
    )
    print(f"Notification sent: {result}")
    
    # Test deduplication
    result2 = route_attention(
        "Mr Gagger Test",
        "Notification with chime, chat link, and budget tracking!",
        speaks=False
    )
    print(f"Duplicate notification sent: {result2}")
    
    print(f"Hourly count: {_hourly_count}")
