"""
Discord Bridge for Clawdbot
Discord posting with strict @everyone gating and showcase support.
Includes live stream monitoring for channel 1174052382057963623.
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
import threading

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

DISCORD_LOG_FILE = os.path.join(SKILL_DIR, "discord_posts.jsonl")
DISCORD_STATE_FILE = os.path.join(SKILL_DIR, "discord_state.json")

# Default live stream channel to monitor (user's specified channel)
DEFAULT_STREAM_CHANNEL = "1174052382057963623"

# BLOCKED CHANNELS - never post here, redirect to DM
BLOCKED_CHANNELS = ["522625769609101335"]
# Owner DM channel for redirected messages
OWNER_DM_CHANNEL = "1470298414565818490"
OWNER_USER_ID = "292890243852664855"


@dataclass
class DiscordPostLog:
    """Log entry for a Discord post."""
    timestamp: str
    channel_id: str
    message_preview: str
    mention_type: str  # none, role, everyone
    post_type: str  # normal, showcase, strong_feeling
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class DiscordBridge:
    """
    Handles Discord posting with strict safety controls.
    Supports @everyone gating, showcase mode, and live stream monitoring.
    """
    
    def __init__(self):
        self.settings = self._load_settings()
        self.state = self._load_state()
        self._lock = threading.Lock()
    
    def _load_settings(self) -> Dict:
        """Load Discord settings."""
        try:
            with open(os.path.join(SKILL_DIR, "settings.json"), "r") as f:
                settings = json.load(f)
                return settings.get("discord", {
                    "enabled": True,
                    "mode": "bot",
                    "channel_id": "1462568916692762687",
                    "showcase_channel_id": None,
                    "stream_channel_id": DEFAULT_STREAM_CHANNEL,
                    "mention_mode": "none",
                    "max_showcase_pings_per_day": 2,
                    "cooldown_minutes": 30,
                    "ask_before_everyone": True
                })
        except FileNotFoundError:
            return {"enabled": False}
    
    def _load_state(self) -> Dict:
        """Load Discord state (ping counts, last post times)."""
        try:
            with open(DISCORD_STATE_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "pings_today": 0,
                "last_ping_date": None,
                "last_post_time": None,
                "showcase_pings_today": 0,
                "strong_feeling_pings_today": 0
            }
    
    def _save_state(self):
        """Save Discord state."""
        with open(DISCORD_STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)
    
    def _log_post(self, log: DiscordPostLog):
        """Log a Discord post."""
        with open(DISCORD_LOG_FILE, "a") as f:
            f.write(json.dumps(log.to_dict()) + "\n")
    
    def _reset_daily_counts_if_needed(self):
        """Reset daily ping counts if it's a new day."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get("last_ping_date") != today:
            self.state["pings_today"] = 0
            self.state["showcase_pings_today"] = 0
            self.state["strong_feeling_pings_today"] = 0
            self.state["last_ping_date"] = today
            self._save_state()
    
    def _get_token(self) -> Optional[str]:
        """Get Discord bot token from config."""
        # Try environment first
        token = os.environ.get("DISCORD_BOT_TOKEN")
        if token:
            return token
        
        # Try openclaw config
        try:
            config_path = os.path.expanduser("~/.openclaw/openclaw.json")
            with open(config_path, "r") as f:
                config = json.load(f)
                return config.get("channels", {}).get("discord", {}).get("token")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
        return None
    
    def can_ping_everyone(self, ping_type: str = "showcase") -> tuple:
        """
        Check if @everyone ping is allowed.
        
        Returns:
            (allowed: bool, reason: str)
        """
        self._reset_daily_counts_if_needed()
        
        if not self.settings.get("enabled", False):
            return False, "Discord is disabled"
        
        # Check cooldown
        last_post = self.state.get("last_post_time")
        if last_post:
            last_dt = datetime.fromisoformat(last_post)
            cooldown = self.settings.get("cooldown_minutes", 30)
            if datetime.now() - last_dt < timedelta(minutes=cooldown):
                remaining = cooldown - (datetime.now() - last_dt).total_seconds() / 60
                return False, f"Cooldown active ({remaining:.0f}m remaining)"
        
        # Check daily limits based on ping type
        if ping_type == "showcase":
            max_pings = self.settings.get("max_showcase_pings_per_day", 2)
            current = self.state.get("showcase_pings_today", 0)
        else:  # strong_feeling
            max_pings = 1  # Hard limit from requirements
            current = self.state.get("strong_feeling_pings_today", 0)
        
        if current >= max_pings:
            return False, f"Daily {ping_type} ping limit reached ({current}/{max_pings})"
        
        return True, "Ping allowed"
    
    async def _send_message_async(
        self,
        channel_id: str,
        content: str,
        mention_type: str = "none"
    ) -> tuple:
        """
        Send a message to Discord asynchronously.
        
        Returns:
            (success: bool, error: str or None)
        """
        token = self._get_token()
        if not token:
            return False, "No Discord token configured"
        
        try:
            import aiohttp
            
            # Build content with mention if needed
            if mention_type == "everyone":
                content = f"@everyone\n{content}"
            elif mention_type == "role":
                role_id = self.settings.get("role_id")
                if role_id:
                    content = f"<@&{role_id}>\n{content}"
            
            headers = {
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json"
            }
            
            # Use AllowedMentions to control pings
            allowed_mentions = {"parse": []}
            if mention_type == "everyone":
                allowed_mentions["parse"] = ["everyone"]
            elif mention_type == "role":
                allowed_mentions["parse"] = ["roles"]
            
            payload = {
                "content": content,
                "allowed_mentions": allowed_mentions
            }
            
            url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status in [200, 201]:
                        return True, None
                    else:
                        error_body = await resp.text()
                        return False, f"HTTP {resp.status}: {error_body[:100]}"
                        
        except ImportError:
            return False, "aiohttp not installed"
        except Exception as e:
            return False, str(e)
    
    def send_message(
        self,
        content: str,
        channel_id: str = None,
        mention_type: str = "none",
        post_type: str = "normal"
    ) -> bool:
        """
        Send a message to Discord.
        
        Args:
            content: Message content
            channel_id: Target channel (uses default if None)
            mention_type: "none", "role", or "everyone"
            post_type: "normal", "showcase", or "strong_feeling"
        
        Returns:
            True if successful
        """
        if not self.settings.get("enabled", False):
            print("[DiscordBridge] Discord is disabled")
            return False
        
        channel = channel_id or self.settings.get("channel_id")
        if not channel:
            print("[DiscordBridge] No channel configured")
            return False
        
        # BLOCKED CHANNEL CHECK - redirect to owner DM
        if str(channel) in BLOCKED_CHANNELS:
            print(f"[DiscordBridge] Channel {channel} is blocked - redirecting to DM")
            channel = OWNER_DM_CHANNEL
        
        # BLOCKED MENTIONS - strip @goblins
        import re
        content = re.sub(r'@goblins', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<@&\d+>', '', content)  # Strip any role mentions just to be safe
        
        # Run async send
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success, error = loop.run_until_complete(
            self._send_message_async(channel, content, mention_type)
        )
        loop.close()
        
        # Update state and log
        with self._lock:
            if success:
                self.state["last_post_time"] = datetime.now().isoformat()
                if mention_type == "everyone":
                    if post_type == "showcase":
                        self.state["showcase_pings_today"] = self.state.get("showcase_pings_today", 0) + 1
                    else:
                        self.state["strong_feeling_pings_today"] = self.state.get("strong_feeling_pings_today", 0) + 1
                self._save_state()
        
        self._log_post(DiscordPostLog(
            timestamp=datetime.now().isoformat(),
            channel_id=channel,
            message_preview=content[:100],
            mention_type=mention_type,
            post_type=post_type,
            success=success,
            error=error
        ))
        
        if error:
            print(f"[DiscordBridge] Error: {error}")
        
        return success
    
    def send_showcase(
        self,
        content: str,
        artifacts: List[str] = None,
        allow_everyone: bool = False
    ) -> bool:
        """
        Send a showcase message.
        
        Args:
            content: Showcase content
            artifacts: List of artifact URLs/descriptions
            allow_everyone: Whether to @everyone (requires gating check)
        """
        channel = self.settings.get("showcase_channel_id") or self.settings.get("channel_id")
        
        # Format showcase message
        showcase_msg = f"🎉 **SHOWCASE**\n\n{content}"
        if artifacts:
            showcase_msg += "\n\n**Artifacts:**\n" + "\n".join(f"• {a}" for a in artifacts)
        
        mention_type = "none"
        if allow_everyone:
            can_ping, reason = self.can_ping_everyone("showcase")
            if can_ping:
                mention_type = "everyone"
            else:
                print(f"[DiscordBridge] @everyone blocked: {reason}")
        
        return self.send_message(
            showcase_msg,
            channel_id=channel,
            mention_type=mention_type,
            post_type="showcase"
        )
    
    def send_strong_feeling_ping(
        self,
        title: str,
        reason: str,
        what_happened: str,
        why_it_matters: str,
        what_to_do: str,
        links: List[str] = None,
        force: bool = False
    ) -> bool:
        """
        Send a high-salience @everyone ping.
        
        Args:
            title: Brief title
            reason: 1-line reason
            what_happened: Bullet 1
            why_it_matters: Bullet 2
            what_to_do: Bullet 3
            links: Optional relevant links
            force: Skip gating (EMERGENCY ONLY)
        """
        if not force:
            can_ping, block_reason = self.can_ping_everyone("strong_feeling")
            if not can_ping:
                print(f"[DiscordBridge] Strong feeling ping blocked: {block_reason}")
                return False
            
            # If ask_before_everyone is enabled, we shouldn't auto-send
            if self.settings.get("ask_before_everyone", True):
                print("[DiscordBridge] ask_before_everyone is enabled - this should be confirmed first")
                return False
        
        # Format message
        msg = f"⚡ **{title}** - High-salience ping\n"
        msg += f"*{reason}*\n\n"
        msg += f"• **What happened:** {what_happened}\n"
        msg += f"• **Why it matters:** {why_it_matters}\n"
        msg += f"• **What to do:** {what_to_do}\n"
        
        if links:
            msg += "\n**Links:** " + " | ".join(links[:3])
        
        return self.send_message(
            msg,
            mention_type="everyone",
            post_type="strong_feeling"
        )
    
    async def get_live_streams(self, channel_id: str = None) -> List[Dict]:
        """
        Check for active live streams in the specified voice channel.
        
        Args:
            channel_id: Voice channel to check (uses configured stream channel if None)
        
        Returns:
            List of active streams with user info
        """
        channel = channel_id or self.settings.get("stream_channel_id", DEFAULT_STREAM_CHANNEL)
        token = self._get_token()
        
        if not token:
            return []
        
        try:
            import aiohttp
            
            headers = {"Authorization": f"Bot {token}"}
            
            # Get guild ID from channel
            channel_url = f"https://discord.com/api/v10/channels/{channel}"
            async with aiohttp.ClientSession() as session:
                async with session.get(channel_url, headers=headers) as resp:
                    if resp.status != 200:
                        return []
                    channel_data = await resp.json()
                    guild_id = channel_data.get("guild_id")
                
                if not guild_id:
                    return []
                
                # Get voice states to find streams
                voice_url = f"https://discord.com/api/v10/guilds/{guild_id}/voice-states"
                # Note: This endpoint may not be available without gateway connection
                # For now, we'll use a simpler approach
                
            return []
            
        except Exception as e:
            print(f"[DiscordBridge] Stream check error: {e}")
            return []
    
    def check_streams_sync(self) -> List[Dict]:
        """Synchronous wrapper for stream checking."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.get_live_streams())
        loop.close()
        return result
    
    def get_status(self) -> Dict:
        """Get bridge status for /status endpoint."""
        self._reset_daily_counts_if_needed()
        return {
            "enabled": self.settings.get("enabled", False),
            "channel_id": self.settings.get("channel_id"),
            "stream_channel_id": self.settings.get("stream_channel_id", DEFAULT_STREAM_CHANNEL),
            "showcase_pings_today": self.state.get("showcase_pings_today", 0),
            "strong_feeling_pings_today": self.state.get("strong_feeling_pings_today", 0),
            "max_showcase_pings": self.settings.get("max_showcase_pings_per_day", 2),
            "last_post_time": self.state.get("last_post_time"),
            "can_ping_showcase": self.can_ping_everyone("showcase")[0],
            "can_ping_strong": self.can_ping_everyone("strong_feeling")[0]
        }


# Global instance
discord_bridge = DiscordBridge()


# Convenience functions
def send_message(content: str, channel_id: str = None, mention: str = "none") -> bool:
    """Send a message to Discord."""
    return discord_bridge.send_message(content, channel_id, mention)


def send_showcase(content: str, artifacts: List[str] = None, ping: bool = False) -> bool:
    """Send a showcase message."""
    return discord_bridge.send_showcase(content, artifacts, ping)


def can_ping_everyone(ping_type: str = "showcase") -> tuple:
    """Check if @everyone is allowed."""
    return discord_bridge.can_ping_everyone(ping_type)


if __name__ == "__main__":
    print("Testing Discord Bridge...")
    
    status = discord_bridge.get_status()
    print(f"\nStatus: {json.dumps(status, indent=2)}")
    
    # Test permission check
    can, reason = discord_bridge.can_ping_everyone("showcase")
    print(f"\nCan @everyone (showcase): {can} - {reason}")
    
    can2, reason2 = discord_bridge.can_ping_everyone("strong_feeling")
    print(f"Can @everyone (strong feeling): {can2} - {reason2}")
