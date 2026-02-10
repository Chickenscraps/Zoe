from typing import List, Dict, Any
from collections import Counter

# Very simple keyword scanner for now.
# In future, this should use LLM to summarize recent chat logs.

TRENDING_TOPICS = [
    "AI", "crypto", "politics", "gaming", "movies", "meme", 
    "tech", "code", "food", "music", "travel"
]

class CultureScanner:
    def __init__(self):
        pass

    def scan_recent_chat(self, messages: List[str]) -> List[str]:
        """Identify trending topics in recent messages."""
        counts = Counter()
        for msg in messages:
            msg_lower = msg.lower()
            for topic in TRENDING_TOPICS:
                if topic.lower() in msg_lower:
                    counts[topic] += 1
        
        # Return top 3
        return [t for t, c in counts.most_common(3)]

culture_scanner = CultureScanner()
