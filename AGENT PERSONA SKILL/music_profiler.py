import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

# Simple regex for music links
MUSIC_PATTERNS = [
    r'(https?://open\.spotify\.com/track/[a-zA-Z0-9]+)',
    r'(https?://www\.youtube\.com/watch\?v=[a-zA-Z0-9_-]+)',
    r'(https?://youtu\.be/[a-zA-Z0-9_-]+)',
    r'(https?://soundcloud\.com/[\w-]+/[\w-]+)'
]

GENRE_KEYWORDS = {
    "lofi": ["lofi", "lo-fi", "chill", "study", "beats"],
    "techno": ["techno", "rave", "acid", "detroit"],
    "house": ["house", "deep house", "tech house"],
    "drum_and_bass": ["dnb", "drum and bass", "jungle", "liquid"],
    "ambient": ["ambient", "drone", "meditation"],
    "hip_hop": ["rap", "hip hop", "trap", "drill"],
    "rock": ["rock", "metal", "punk", "indie"],
    "pop": ["pop", "top 40", "chart"],
    "classical": ["classical", "piano", "orchestra"]
}

class MusicProfiler:
    def __init__(self):
        self.patterns = [re.compile(p) for p in MUSIC_PATTERNS]

    def extract_links(self, text: str) -> List[str]:
        """Extract music links from text."""
        links = []
        for pattern in self.patterns:
            links.extend(pattern.findall(text))
        return list(set(links))

    def identify_genre(self, text: str, url: str = None) -> str:
        """
        Identify genre from text context or URL metadata (future).
        Currently uses simple keyword matching on the text.
        """
        text_lower = text.lower()
        
        # Check keywords
        scores = {g: 0 for g in GENRE_KEYWORDS}
        for genre, keywords in GENRE_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[genre] += 1
        
        # Return best match if score > 0
        best_genre = max(scores, key=scores.get)
        if scores[best_genre] > 0:
            return best_genre
            
        return "unknown"

    def get_music_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user's music profile (placeholder for DB integration)."""
        # In future, fetch from memory_store.user_profile
        return {"top_genres": [], "recent_links": []}

music_profiler = MusicProfiler()

if __name__ == "__main__":
    text = "Yo check out this sick dnb track https://youtu.be/dQw4w9WgXcQ"
    print(f"Text: {text}")
    print(f"Links: {music_profiler.extract_links(text)}")
    print(f"Genre: {music_profiler.identify_genre(text)}")
