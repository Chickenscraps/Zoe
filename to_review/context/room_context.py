import json
from datetime import datetime, timezone
from typing import List, Dict, Optional
from safety_layer.sanitize import sanitize_inbound_text

class RoomContextBuilder:
    """
    Builds the ROOM_CONTEXT object from message history.
    Includes heuristics for topic and tone.
    """
    
    TRADING_KEYWORDS = {'pnl', 'trade', 'spread', 'iv', 'delta', 'options', 'spy', 'nvda', 'qqq'}
    CLEANUP_KEYWORDS = {'desktop', 'downloads', 'folder', 'rename', 'explorer', 'cleanup', 'organize'}
    DEBUG_KEYWORDS = {'bug', 'error', 'stack', 'fix', 'broken', 'restart', 'logs'}
    PLAN_KEYWORDS = {'plan', 'premarket', 'gameplan', 't-15', 't-10', 't-5', 'forecast'}

    @staticmethod
    def detect_topic(messages: List[str]) -> str:
        text = " ".join(messages).lower()
        if any(w in text for w in RoomContextBuilder.TRADING_KEYWORDS): return "trading"
        if any(w in text for w in RoomContextBuilder.CLEANUP_KEYWORDS): return "cleanup"
        if any(w in text for w in RoomContextBuilder.DEBUG_KEYWORDS): return "debug"
        if any(w in text for w in RoomContextBuilder.PLAN_KEYWORDS): return "plan"
        return "banter"

    @staticmethod
    def detect_tone(messages: List[str]) -> str:
        text = " ".join(messages).lower()
        if any(w in text for w in ['lol', 'lmao', '🤣', '😂', 'chill', 'haha']): return "chill"
        if any(w in text for w in ['hurry', 'stressed', 'wtf', 'broken', 'reboot', 'panic']): return "chaotic"
        if any(w in text for w in ['lock in', 'focus', 'execute', 'serious']): return "locked-in"
        if any(w in text for w in ['profit', 'green', 'win', 'nice', 'print', 'bullish']): return "hyped"
        return "neutral"

    @classmethod
    def build(cls, channel_id: int, guild_id: Optional[int], messages: List[Dict]) -> str:
        """
        Builds the ROOM_CONTEXT JSON string.
        messages expected to be: [{author, role, ts, text}]
        """
        # participants (max 6)
        participants = list(set(m['author'] for m in messages))[:6]
        
        # summary & topic
        texts = [m['text'] for m in messages]
        topic = cls.detect_topic(texts)
        tone = cls.detect_tone(texts)
        
        # room_summary: 1-2 sentences grounded in texts
        summary = f"The group is discussing {topic} matters. The vibe seems {tone}."
        if topic == "debug":
            summary = f"You are assisting with system stability and debugging. Vibe: {tone}."
        elif topic == "trading":
            summary = f"Market analysis and trading setups are being evaluated. Vibe: {tone}."
        elif topic == "cleanup":
            summary = f"File system organization and workspace cleanup are in progress. Vibe: {tone}."

        context = {
            "channel_id": str(channel_id),
            "guild_id": str(guild_id) if guild_id else None,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "participants": participants,
            "last_messages": messages[-10:], # last 10
            "room_summary": summary,
            "active_topic": topic,
            "tone": tone
        }
        
        return json.dumps(context, indent=2)

def prepare_message_for_context(author: str, role: str, text: str) -> Dict:
    """Prepares a single message record."""
    return {
        "author": author,
        "role": role,
        "ts": datetime.now(timezone.utc).isoformat(),
        "text": sanitize_inbound_text(text)
    }
