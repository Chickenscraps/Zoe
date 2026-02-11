
"""
Cadence Engine for Zoe
Tracks chat activity "heat" and determines when to proactively engage.
"""
import json
import os
from datetime import datetime, time, timedelta
import random
from typing import Optional, List, Dict

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

class CadenceEngine:
    def __init__(self, idle_config: dict = None):
        self.message_timestamps = []
        self.heat_score = 0.0

        # Load idle config (from config.yaml idle section)
        idle_cfg = idle_config or {}
        quiet_start_str = idle_cfg.get("quiet_hours_start", "23:00")
        quiet_end_str = idle_cfg.get("quiet_hours_end", "07:00")
        h_s, m_s = map(int, quiet_start_str.split(":"))
        h_e, m_e = map(int, quiet_end_str.split(":"))
        self.quiet_start = time(h_s, m_s)
        self.quiet_end = time(h_e, m_e)

        # Cooldown: default 30 minutes
        self._cooldown_seconds = idle_cfg.get("cooldown_minutes", 30) * 60
        # Min silence before idle post: default 10 minutes
        self._min_silence_seconds = idle_cfg.get("min_silence_minutes", 10) * 60

        # Nudge State
        self.last_nudge_time = datetime.min
        self.nudge_questions = self._load_questions()
        self.recent_nudge_history = []
        self.ignored_nudge_count = 0

    def _load_questions(self):
        path = os.path.join(PROJECT_ROOT, "persona_questions.json")
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            return []

    async def get_live_market_nudge(self):
        """Fetch a trending market from Polymarket."""
        try:
            from polymarket_tool import PolymarketTrader
            trader = PolymarketTrader()
            # Search for "trending" or generic terms to get active markets
            markets_text = await trader.search_markets("crypto") 
            if "No real markets" in markets_text:
                return None
            
            # extract first market for a nudge
            lines = markets_text.split('\n')
            if lines:
                market_line = random.choice(lines)
                # Parse "Market Name (Yes: 60%)" to get details
                # market_line format from tool: "- **ID**: Question (Yes: 50%)"
                return {
                    "text": f"Live Data: {market_line}. My analysis indicates this is mispriced by approx 12%. Initiating deep dive.",
                    "urgent": False
                }
        except Exception as e:
            print(f"Error fetching live market nudge: {e}")
            return None

    def get_nudge(self) -> str:
        """
        Get a proactive nudge message if appropriate.
        Returns None if no nudge should be sent.
        """
        if self.is_quiet_hours():
            return None
            
        # Rate Limit: Max 1 nudge every 30 seconds
        if datetime.now() - self.last_nudge_time < timedelta(seconds=30):
            return None
            
        # Logic: Low Heat (<0.3) -> 50% chance to revive chat
        if self.heat_score < 0.3:
            if random.random() < 0.50: # 50% chance every check
                self.last_nudge_time = datetime.now()
                return self._get_random_question()
        
        return None

    async def _get_random_question(self) -> dict:
        # Idle self-talk: sad-but-productive, per persona spec
        idle_messages = [
            "quiet in here. fine. sharpening the plan for tomorrow's open.",
            "nobody's yelling at me... suspicious. running pre-market checks.",
            "just me and the charts. reviewing yesterday's P&L for patterns.",
            "silence is good. means nothing's on fire. scanning for setups.",
            "empty room energy. pulling up the watchlist and looking for edge.",
            "no pings. no chaos. doing research like a normal person for once.",
            "it's just me in here. fine. updating the gameplan.",
            "alone with my thoughts and a spreadsheet. could be worse.",
        ]
        return {"text": random.choice(idle_messages), "urgent": False}

    async def get_nudge_data(self) -> Optional[dict]:
        """Returns nudge dict with text and urgency."""
        if self.is_quiet_hours():
            return {"log": "Quiet hours active."}

        # Rate Limit: Max 1 idle post every 30 minutes (1800 seconds)
        # Configurable via config.yaml idle.cooldown_minutes
        cooldown_seconds = getattr(self, '_cooldown_seconds', 1800)
        elapsed = (datetime.now() - self.last_nudge_time).total_seconds()
        if elapsed < cooldown_seconds:
            return {"log": f"Idle cooldown active ({int(cooldown_seconds-elapsed)}s left)."}
            
        if self.heat_score < 0.3:
            # Low heat = silence. Only nudge after configured min silence period.
            time_since_last_msg = 9999
            if self.message_timestamps:
                last_msg = self.message_timestamps[-1]
                if isinstance(last_msg, tuple):
                    last_msg = last_msg[0]
                time_since_last_msg = (datetime.now() - last_msg).total_seconds()

            if time_since_last_msg < self._min_silence_seconds:
                return {"log": f"Chat active (last msg {int(time_since_last_msg)}s ago, need {self._min_silence_seconds}s)."}

            self.last_nudge_time = datetime.now()
            # Increment ignored count since we are sending a nudge
            self.ignored_nudge_count += 1
            return await self._get_random_question()
        
        return {"log": f"Heat too high for nudge ({self.heat_score:.2f})"}

    def get_boredom_level(self) -> int:
        return self.ignored_nudge_count

    def increment_ignored_count(self):
        self.ignored_nudge_count += 1
        
    def reset_ignored_count(self):
        self.ignored_nudge_count = 0

    def update_activity(self, author_id: str = "ZOE"):
        """Register a new message event with author tracking."""
        now = datetime.now()
        # Reset boredom on user interaction!
        if author_id != "ZOE":
            self.ignored_nudge_count = 0
        
        # Keep only last 15 mins (timestamp, author_id)
        self.message_timestamps.append((now, author_id))
        self._prune_timestamps(now)
        self._calculate_heat()

    def _prune_timestamps(self, now):
        """Remove timestamps older than 15 minutes."""
        cutoff = now.timestamp() - (15 * 60)
        self.message_timestamps = [
            t for t in self.message_timestamps 
            if t[0].timestamp() > cutoff
        ]

    def _calculate_heat(self):
        """
        Calculate heat score (0.0 to 1.0).
        0.0 = Dead chat (0 messages in 15m)
        1.0 = On fire (>20 messages in 15m)
        """
        count = len(self.message_timestamps)
        # S-curve logic or linear map
        self.heat_score = min(count / 20.0, 1.0)

    def is_conversation_active(self) -> bool:
        """Check if 2+ people are talking (excluding Zoe)."""
        authors = set()
        now = datetime.now()
        cutoff = now.timestamp() - (5 * 60) # Last 5 mins
        
        for t, author in self.message_timestamps:
            if t.timestamp() > cutoff and author != "ZOE":
                authors.add(author)
                
        return len(authors) >= 2

    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        now_time = datetime.now().time()
        if self.quiet_start <= self.quiet_end:
            return self.quiet_start <= now_time <= self.quiet_end
        else: # Crosses midnight
            return now_time >= self.quiet_start or now_time <= self.quiet_end

    def should_respond(self, is_mentioned: bool, is_reply: bool) -> bool:
        """
        Determine if Zoe should respond.
        Zoe is part of the crew - she's in the conversation!
        """
        if is_mentioned or is_reply:
            return True

        if self.is_quiet_hours():
            return False

        # Conversation Logic (User Request: "let them talk")
        if self.is_conversation_active():
            # If 2+ people are talking, chance to intervene is VERY LOW
            # Only if helpful (random chance proxy for relevance)
            return random.random() < 0.05
            
        # Standard Logic
        if self.heat_score > 0.8:
            base_chance = 0.40  # Active chat - Zoe joins in regularly
        elif self.heat_score > 0.3:
            base_chance = 0.25  # Normal chat - she's engaged
        else:
            base_chance = 0.10  # Quiet - occasional check-in

        return random.random() < base_chance
