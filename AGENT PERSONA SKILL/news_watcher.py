"""
News Watcher for Clawdbot
Hourly headline check with jitter, valence scoring, and mood influence.
"""
import os
import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_CACHE_FILE = os.path.join(SKILL_DIR, "latest_news.json")
NEWS_LOG_FILE = os.path.join(SKILL_DIR, "news_history.jsonl")
NEWS_SOURCES_FILE = os.path.join(SKILL_DIR, "news_sources.json")

# Default RSS feeds
DEFAULT_FEEDS = [
    {"name": "Hacker News", "url": "https://news.ycombinator.com/rss", "category": "tech"},
    {"name": "Reuters Top", "url": "https://feeds.reuters.com/reuters/topNews", "category": "world"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "tech"},
]

# Keywords for valence scoring (positive/negative sentiment)
POSITIVE_KEYWORDS = [
    "breakthrough", "success", "growth", "innovation", "milestone",
    "achievement", "progress", "improvement", "recovery", "optimistic",
    "wins", "launch", "discover", "advance", "promising"
]

NEGATIVE_KEYWORDS = [
    "crisis", "crash", "failure", "decline", "warning", "threat",
    "collapse", "disaster", "attack", "breach", "layoffs", "fraud",
    "scandal", "tension", "conflict", "recession", "shutdown"
]

# Importance keywords
IMPORTANCE_KEYWORDS = [
    "breaking", "urgent", "major", "critical", "unprecedented",
    "historic", "exclusive", "developing", "emergency"
]

@dataclass
class NewsItem:
    """Single news item."""
    title: str
    source: str
    url: str
    published: Optional[str] = None
    summary: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class NewsPulse:
    """Aggregated news pulse."""
    timestamp: str
    items: List[Dict]
    topics: List[str]
    valence: float  # -1.0 to +1.0
    importance: float  # 0.0 to 1.0
    summary_2_lines: str
    
    def to_dict(self) -> Dict:
        return asdict(self)

def _load_feeds() -> List[Dict]:
    """Load RSS feed sources."""
    try:
        with open(NEWS_SOURCES_FILE, "r") as f:
            config = json.load(f)
            return config.get("feeds", DEFAULT_FEEDS)
    except FileNotFoundError:
        return DEFAULT_FEEDS

def _calculate_valence(text: str) -> float:
    """
    Calculate sentiment valence from text.
    Returns -1.0 (very negative) to +1.0 (very positive)
    """
    text_lower = text.lower()
    
    positive_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    negative_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    
    total = positive_count + negative_count
    if total == 0:
        return 0.0  # Neutral
    
    valence = (positive_count - negative_count) / total
    return max(-1.0, min(1.0, valence))

def _calculate_importance(text: str) -> float:
    """
    Calculate importance score from text.
    Returns 0.0 to 1.0
    """
    text_lower = text.lower()
    
    importance_count = sum(1 for kw in IMPORTANCE_KEYWORDS if kw in text_lower)
    
    # Normalize to 0-1 range
    return min(1.0, importance_count * 0.25)

def _extract_topics(items: List[Dict]) -> List[str]:
    """Extract main topics from news items."""
    # Simple topic extraction based on common nouns/themes
    topic_keywords = ["AI", "tech", "economy", "politics", "science", "business", "crypto", "climate"]
    found_topics = set()
    
    for item in items:
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        for topic in topic_keywords:
            if topic.lower() in text:
                found_topics.add(topic)
    
    return list(found_topics)[:5]

def _generate_summary(items: List[Dict]) -> str:
    """Generate a 2-line summary of the news pulse."""
    if not items:
        return "No news available at the moment."
    
    # Take top 2 headlines
    summaries = []
    for item in items[:2]:
        title = item.get("title", "")[:80]
        source = item.get("source", "")
        summaries.append(f"• {title} ({source})")
    
    return "\n".join(summaries)

def fetch_headlines(max_per_source: int = 3) -> Optional[NewsPulse]:
    """
    Fetch headlines from all configured RSS sources.
    
    Args:
        max_per_source: Maximum headlines to take from each source
    
    Returns:
        NewsPulse object or None on failure
    """
    try:
        from web_access import rss_fetch
    except ImportError:
        print("[NewsWatcher] web_access module not available")
        return None
    
    feeds = _load_feeds()
    all_items = []
    
    for feed in feeds:
        try:
            items = rss_fetch(feed["url"])
            for item in items[:max_per_source]:
                all_items.append({
                    "title": item.get("title", ""),
                    "source": feed["name"],
                    "url": item.get("link", ""),
                    "published": item.get("published", ""),
                    "summary": item.get("summary", "")[:200]
                })
        except Exception as e:
            print(f"[NewsWatcher] Error fetching {feed['name']}: {e}")
    
    if not all_items:
        return None
    
    # Calculate aggregate valence and importance
    all_text = " ".join([
        f"{item['title']} {item.get('summary', '')}" for item in all_items
    ])
    
    valence = _calculate_valence(all_text)
    importance = _calculate_importance(all_text)
    topics = _extract_topics(all_items)
    summary = _generate_summary(all_items)
    
    pulse = NewsPulse(
        timestamp=datetime.now().isoformat(),
        items=all_items,
        topics=topics,
        valence=valence,
        importance=importance,
        summary_2_lines=summary
    )
    
    return pulse

def save_pulse(pulse: NewsPulse):
    """Save the latest news pulse to cache."""
    with open(NEWS_CACHE_FILE, "w") as f:
        json.dump(pulse.to_dict(), f, indent=2)
    
    # Also log to history
    with open(NEWS_LOG_FILE, "a") as f:
        f.write(json.dumps(pulse.to_dict()) + "\n")

def load_latest_pulse() -> Optional[NewsPulse]:
    """Load the latest cached news pulse."""
    try:
        with open(NEWS_CACHE_FILE, "r") as f:
            data = json.load(f)
            return NewsPulse(**data)
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return None

def format_for_feed(pulse: NewsPulse, max_headlines: int = 5) -> str:
    """
    Format news pulse for the Proactive Feed.
    Includes clickable links.
    """
    if not pulse.items:
        return "🗞️ No headlines available right now."
    
    lines = ["🗞️ **Headline Pulse**\n"]
    lines.append(pulse.summary_2_lines)
    lines.append("")
    
    for item in pulse.items[:max_headlines]:
        title = item["title"][:60]
        source = item["source"]
        url = item["url"]
        lines.append(f"• [{title}...]({url}) — {source}")
    
    if pulse.topics:
        lines.append(f"\n📌 Topics: {', '.join(pulse.topics)}")
    
    return "\n".join(lines)

def format_for_toast(pulse: NewsPulse) -> tuple:
    """
    Format news pulse for toast notification.
    Returns (title, message)
    """
    if not pulse.items:
        return ("📰 News Check", "Nothing major happening right now.")
    
    top_item = pulse.items[0]
    title = "🗞️ Headline Alert" if pulse.importance > 0.5 else "📰 News Pulse"
    message = f"{top_item['title'][:80]}... ({top_item['source']})"
    
    return (title, message)

class NewsWatcher:
    """
    Watches news and posts to proactive feed.
    Runs hourly with jitter.
    """
    
    def __init__(self):
        self.check_interval_minutes = 60
        self.jitter_minutes = 10
        self.last_check = None
        self.daily_influence_budget = 0.10  # Max ±10% mood influence per day
        self.influence_used_today = 0.0
        self.last_reset_date = datetime.now().date()
    
    def _reset_daily_budget(self):
        """Reset daily influence budget if it's a new day."""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.influence_used_today = 0.0
            self.last_reset_date = today
    
    def should_check(self) -> bool:
        """Check if it's time for a news check."""
        if self.last_check is None:
            return True
        
        # Add jitter
        jitter = random.randint(-self.jitter_minutes, self.jitter_minutes)
        interval = timedelta(minutes=self.check_interval_minutes + jitter)
        
        return datetime.now() - self.last_check >= interval
    
    def check_and_publish(self) -> Optional[NewsPulse]:
        """
        Check news and publish to event bus.
        Returns the pulse if check was performed.
        """
        if not self.should_check():
            return None
        
        pulse = fetch_headlines()
        if not pulse:
            return None
        
        self.last_check = datetime.now()
        save_pulse(pulse)
        
        # Apply mood influence
        self._apply_mood_influence(pulse)
        
        # Publish to event bus
        try:
            from event_bus import event_bus, Event, EventType, Urgency
            
            # Determine urgency based on importance
            urgency = Urgency.HIGH if pulse.importance > 0.7 else Urgency.NORMAL
            
            event = Event(
                event_type=EventType.NEWS_PULSE.value,
                payload=pulse.to_dict(),
                source="news_watcher"
            )
            event_bus.publish(event)
            
            # If high importance, also emit agent_wants_user
            if pulse.importance > 0.7:
                title, message = format_for_toast(pulse)
                event_bus.publish_agent_wants_user(
                    title=title,
                    message=message,
                    urgency=urgency,
                    source="news_watcher"
                )
        except ImportError:
            print("[NewsWatcher] Event bus not available")
        
        return pulse
    
    def _apply_mood_influence(self, pulse: NewsPulse):
        """
        Apply news-based mood bias (within daily caps).
        """
        self._reset_daily_budget()
        
        # Only influence if there's remaining budget
        remaining_budget = self.daily_influence_budget - abs(self.influence_used_today)
        if remaining_budget <= 0:
            return
        
        # Only significant news affects mood
        if pulse.importance < 0.5:
            return
        
        # Calculate influence (capped)
        influence = pulse.valence * 0.02 * pulse.importance  # Small influence
        influence = max(-remaining_budget, min(remaining_budget, influence))
        
        if abs(influence) < 0.01:
            return
        
        self.influence_used_today += influence
        
        try:
            from mood_engine import mood_engine
            mood_engine.apply_news_bias(pulse.valence, pulse.importance)
        except ImportError:
            pass
    
    def get_status(self) -> Dict:
        """Get watcher status for /status endpoint."""
        latest = load_latest_pulse()
        return {
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "latest_pulse_time": latest.timestamp if latest else None,
            "news_available": latest is not None,
            "influence_used_today": self.influence_used_today
        }

# Global instance
news_watcher = NewsWatcher()

# Convenience functions
def check_news() -> Optional[NewsPulse]:
    """Check news if due."""
    return news_watcher.check_and_publish()

def get_latest_news() -> Optional[Dict]:
    """Get the latest cached news pulse."""
    pulse = load_latest_pulse()
    return pulse.to_dict() if pulse else None

if __name__ == "__main__":
    # Test
    print("Testing News Watcher...")
    
    pulse = fetch_headlines()
    if pulse:
        print(f"\n📰 Got {len(pulse.items)} headlines")
        print(f"Valence: {pulse.valence:.2f}")
        print(f"Importance: {pulse.importance:.2f}")
        print(f"Topics: {pulse.topics}")
        print(f"\n{format_for_feed(pulse, max_headlines=3)}")
    else:
        print("No news available")
