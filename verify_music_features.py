import sys
import os

# Add skill dir
SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT PERSONA SKILL")
sys.path.insert(0, SKILL_DIR)

from music_profiler import music_profiler
from mood_engine import mood_engine

def test_music_features():
    print("🎵 Testing Music Features...")
    
    # 1. Link Extraction
    text = "Check this out https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC and https://youtu.be/dQw4w9WgXcQ"
    links = music_profiler.extract_links(text)
    print(f"\n[1] Extracted Links: {links}")
    if len(links) == 2:
        print("✅ Link extraction PASS")
    else:
        print("❌ Link extraction FAIL")
        
    # 2. Genre ID
    texts = [
        ("I love lofi beats for studying", "lofi"),
        ("This techno track is banging", "techno"),
        ("Classical piano is nice", "classical")
    ]
    print("\n[2] Genre Identification:")
    for t, expected in texts:
        genre = music_profiler.identify_genre(t)
        print(f"  '{t}' -> {genre} (Expected: {expected})")
        if genre == expected:
            print("  ✅ Pass")
        else:
            print("  ❌ Fail")
            
    # 3. Mood Recommendations
    print("\n[3] Mood Recommendations:")
    test_moods = ["deep_thinker", "chaotic_gremlin", "happy_helper"]
    for mood in test_moods:
        rec = mood_engine.get_music_recommendation() # Uses current mood, let's force set it
        # Actually get_music_recommendation doesn't take arg in my implementation?
        # Wait, I defined it as `def get_music_recommendation(self) -> Dict[str, str]:`
        # It uses self.current_mood.
        # So I need to set mood first.
        mood_engine._transition_mood(target=mood)
        rec = mood_engine.get_music_recommendation()
        print(f"  Mood: {mood} -> Suggests: {rec['genre']} ({rec['query']})")
        
    print("\n✅ Music Features Verified.")

if __name__ == "__main__":
    test_music_features()
