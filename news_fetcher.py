"""
News Fetcher for Clawdbot
Fetches daily news headlines to keep bot contextually aware
"""
import os
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import aiohttp

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
NEWS_CACHE_FILE = PROJECT_ROOT / "news_cache.json"

# Free news APIs (no key required for basic use)
NEWS_SOURCES = {
    "hackernews": "https://hacker-news.firebaseio.com/v0/topstories.json",
    "hackernews_item": "https://hacker-news.firebaseio.com/v0/item/{}.json",
}

# ============================================================================
# News Fetcher
# ============================================================================

async def fetch_hackernews_top(limit: int = 10) -> List[Dict]:
    """Fetch top stories from Hacker News."""
    stories = []
    
    async with aiohttp.ClientSession() as session:
        # Get top story IDs
        async with session.get(NEWS_SOURCES["hackernews"]) as resp:
            if resp.status != 200:
                return []
            story_ids = await resp.json()
        
        # Fetch story details
        for story_id in story_ids[:limit]:
            url = NEWS_SOURCES["hackernews_item"].format(story_id)
            async with session.get(url) as resp:
                if resp.status == 200:
                    story = await resp.json()
                    if story and story.get("title"):
                        stories.append({
                            "title": story.get("title"),
                            "url": story.get("url", ""),
                            "score": story.get("score", 0),
                            "source": "hackernews",
                            "time": datetime.fromtimestamp(story.get("time", 0)).isoformat()
                        })
    
    return stories


async def fetch_all_news() -> Dict:
    """Fetch news from all sources."""
    news = {
        "fetched_at": datetime.now().isoformat(),
        "stories": []
    }
    
    # Hacker News (tech/startup focused)
    hn_stories = await fetch_hackernews_top(15)
    news["stories"].extend(hn_stories)
    
    return news


def save_news_cache(news: Dict):
    """Save news to cache file."""
    with open(NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(news, f, indent=2)
    print(f"📰 Cached {len(news['stories'])} stories")


def load_news_cache() -> Optional[Dict]:
    """Load news from cache."""
    if not NEWS_CACHE_FILE.exists():
        return None
    
    with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def is_cache_fresh(max_age_hours: int = 6) -> bool:
    """Check if cache is fresh enough."""
    cache = load_news_cache()
    if not cache:
        return False
    
    fetched_at = datetime.fromisoformat(cache["fetched_at"])
    age = datetime.now() - fetched_at
    return age < timedelta(hours=max_age_hours)


def get_news_summary() -> str:
    """Get a summary of current news for the system prompt."""
    cache = load_news_cache()
    if not cache:
        return ""
    
    stories = cache.get("stories", [])[:10]
    if not stories:
        return ""
    
    headlines = [f"- {s['title']}" for s in stories]
    
    return f"""
CURRENT NEWS (as of {cache['fetched_at'][:10]}):
{chr(10).join(headlines)}
"""


async def refresh_news_if_needed():
    """Refresh news cache if stale."""
    if not is_cache_fresh():
        print("📰 Refreshing news cache...")
        news = await fetch_all_news()
        save_news_cache(news)
        return True
    return False


# ============================================================================
# Novelty Engine (Relevance Scoring)
# ============================================================================

# Keywords that boost relevance for the Goblins group
INTEREST_KEYWORDS = {
    "gaming": ["gta", "valve", "steam", "nintendo", "playstation", "xbox", "game", "gaming", "esports"],
    "crypto": ["bitcoin", "ethereum", "crypto", "blockchain", "nft", "defi", "trading"],
    "ai": ["openai", "gpt", "ai", "machine learning", "chatgpt", "claude", "gemini"],
    "tech": ["apple", "google", "microsoft", "meta", "startup", "ipo", "layoffs"],
    "memes": ["doom", "linux", "hack", "wild", "insane", "crazy"],
}

def calculate_relevance(headline: str, user_interests: list = None) -> float:
    """
    Calculate relevance score for a headline.
    Higher = more relevant to share.
    """
    headline_lower = headline.lower()
    score = 0.0
    
    # Check against interest keywords
    interests_to_check = user_interests or list(INTEREST_KEYWORDS.keys())
    
    for category in interests_to_check:
        if category in INTEREST_KEYWORDS:
            for keyword in INTEREST_KEYWORDS[category]:
                if keyword in headline_lower:
                    score += 2.0
                    break  # Only count category once
    
    # Boost for certain "wild" patterns
    wild_patterns = ["first ever", "broke", "record", "million", "billion", "leaked", "announced"]
    for pattern in wild_patterns:
        if pattern in headline_lower:
            score += 1.5
            break
    
    return min(score, 10.0)  # Cap at 10


def get_wild_item(threshold: float = 4.0) -> Optional[Dict]:
    """
    Get the highest-relevance item from cache if above threshold.
    Used by Novelty Engine for proactive sharing.
    """
    cache = load_news_cache()
    if not cache:
        return None
    
    stories = cache.get("stories", [])
    if not stories:
        return None
    
    # Score all stories
    scored = []
    for story in stories:
        score = calculate_relevance(story.get("title", ""))
        if score >= threshold:
            scored.append({**story, "relevance_score": score})
    
    if not scored:
        return None
    
    # Return highest scored
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    return {
        "title": scored[0]["title"],
        "link": scored[0].get("url", ""),
        "score": scored[0]["relevance_score"]
    }


# ============================================================================
# CLI / Test
# ============================================================================

async def main():
    """Fetch and display news."""
    print("📰 Fetching news...")
    news = await fetch_all_news()
    save_news_cache(news)
    
    print(f"\n📰 Top Stories ({len(news['stories'])}):")
    for story in news["stories"][:10]:
        print(f"  • {story['title']}")
    
    print("\n" + get_news_summary())


if __name__ == "__main__":
    asyncio.run(main())
