import os
import random
import aiohttp
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class CaptionGenerator:
    """Generates witty, dark-humor captions for trade events."""
    
    TEMPLATES = {
        "TRADE_OPEN": [
            "Clocked in. Paper account’s about to learn manners. 📉🔪",
            "Locked and loaded. Let's see if the market has a spine today.",
            "Deploying capital. Trying not to yawn while I print.",
            "New position live. Don't blink or you'll miss the entries.",
            "Market's looking soft. Time to exploit."
        ],
        "TRADE_CLOSE_GREEN": [
            "Profit secured. Cigarette lit. Next.",
            "Money printer went brrr. Taking my cut.",
            "Green looks good on us. On to the next victim.",
            "Closed for a win. Purely deterministic, obviously.",
            "Winner. I make this look easy because it is."
        ],
        "TRADE_CLOSE_RED": [
            "That one cost tuition. We’re smarter now. 🚬",
            "Risk managed. Stop hit. Moving on before I get bored.",
            "Red trade. I'll make it back in ten minutes.",
            "Loss taken. Still up on the week. Relax.",
            "Market had a mood swing. I'm over it."
        ],
        "RISK_EVENT": [
            "PDT threshold approaching. I'm watching you.",
            "Risk limits tested. Aborting the wimpy plays.",
            "Major volatility detected. Stay sharp or get out.",
            "Safety protocols active. No heroes today."
        ]
    }

    @staticmethod
    def get_caption(event_type: str) -> str:
        options = CaptionGenerator.TEMPLATES.get(event_type, ["Trading event logged."])
        return random.choice(options)

class GifPicker:
    """Selects relevant GIFs using Tenor API or local fallbacks."""
    
    API_KEY = os.getenv("TENOR_API_KEY")
    
    QUERIES = {
        "TRADE_OPEN": ["locked in", "time to work", "let's go", "suit up"],
        "TRADE_CLOSE_GREEN": ["money printer", "mission accomplished", "victory dance", "cigar", "wolf of wall street"],
        "TRADE_CLOSE_RED": ["pain", "we learn", "facepalm", "cigarette", "this is fine"],
        "RISK_EVENT": ["danger", "abort", "panic button", "security"]
    }

    FALLBACKS = {
        "TRADE_OPEN": ["https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJmZ2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/l0HlxO0Ok3R2/giphy.gif"],
        "TRADE_CLOSE_GREEN": ["https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJmZ2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5Z2Y5JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/3o7TKSjPqcKUIW7Xiw/giphy.gif"]
    }

    async def get_gif(self, event_type: str) -> Optional[str]:
        """Fetch a GIF URL from Tenor or fallback."""
        if not self.API_KEY:
            return random.choice(self.FALLBACKS.get(event_type, [None]))

        query = random.choice(self.QUERIES.get(event_type, ["trading"]))
        url = f"https://tenor.googleapis.com/v2/search?q={query}&key={self.API_KEY}&client_key=zoe_bot&limit=1&media_filter=gif&contentfilter=low"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            return results[0]["media_formats"]["gif"]["url"]
        except Exception as e:
            logger.warning(f"⚠️ Tenor GIF fetch failed: {e}")
            
        return random.choice(self.FALLBACKS.get(event_type, [None]))

gif_picker = GifPicker()
