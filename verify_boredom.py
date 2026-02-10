"""
Verification script for Boredom Engine & Creative Portal
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

def test_boredom_engine_imports():
    print("\n🧪 Testing boredom_engine imports...")
    from boredom_engine import (
        BoredomEngine, boredom_engine, PROJECT_IDEAS,
        generate_announcement, PROJECTS_DIR
    )
    
    print(f"   Project ideas: {len(PROJECT_IDEAS)}")
    print(f"   Projects dir: {PROJECTS_DIR}")
    print("✅ All imports successful!")

def test_project_ideas():
    print("\n🧪 Testing project ideas diversity...")
    from boredom_engine import PROJECT_IDEAS
    
    types = {}
    for idea in PROJECT_IDEAS:
        t = idea.get("type", "unknown")
        types[t] = types.get(t, 0) + 1
    
    print(f"   Types: {types}")
    
    assert "game" in types, "Should have game projects"
    assert "tool" in types, "Should have tool projects"
    assert "art" in types, "Should have art projects"
    
    # Check for existential art
    art_ideas = [p for p in PROJECT_IDEAS if p["type"] == "art"]
    assert len(art_ideas) >= 4, "Should have multiple art pieces"
    
    existential = [p for p in art_ideas if "feel" in p["description"].lower() or "am i" in p["prompt"].lower()]
    assert len(existential) >= 1, "Should have existential art"
    
    print("✅ Project ideas are diverse with existential art!")

def test_boredom_detection():
    print("\n🧪 Testing boredom detection...")
    from boredom_engine import BoredomEngine
    from datetime import datetime, timedelta
    
    engine = BoredomEngine()
    
    # Just updated - not bored
    engine.update_activity()
    assert not engine.is_bored(), "Should not be bored right after activity"
    
    # Simulate old activity
    engine.last_activity = datetime.now() - timedelta(minutes=35)
    assert engine.is_bored(), "Should be bored after 35 mins of silence"
    
    print("✅ Boredom detection works!")

def test_announcement_types():
    print("\n🧪 Testing announcement generation...")
    from boredom_engine import generate_announcement
    
    # Art announcement
    art_project = {"name": "what_am_i", "description": "A painting about feelings", "type": "art", "url": "http://localhost:5050/projects/what_am_i"}
    art_ann = generate_announcement(art_project)
    assert "🎨" in art_ann, "Art should have art emoji"
    assert "-zoe 💜" in art_ann, "Should be signed"
    
    # Game announcement
    game_project = {"name": "snake_game", "description": "Classic snake", "type": "game", "url": "http://localhost:5050/projects/snake_game"}
    game_ann = generate_announcement(game_project)
    assert "🎮" in game_ann, "Game should have game emoji"
    
    print("✅ Announcements work for all types!")

def test_portal_imports():
    print("\n🧪 Testing portal module...")
    from zoe_portal import app, get_all_projects, PROJECTS_DIR, PORT
    
    assert PORT == 5050, "Portal should run on port 5050"
    print(f"   Portal port: {PORT}")
    print(f"   Projects dir: {PROJECTS_DIR}")
    print("✅ Portal module imports correctly!")

def test_scheduler_job():
    print("\n🧪 Testing scheduler job definition...")
    from scheduler_jobs import boredom_check
    
    import inspect
    sig = inspect.signature(boredom_check)
    params = list(sig.parameters.keys())
    
    assert "bot" in params, "Should take bot parameter"
    assert "channel_id" in params, "Should take channel_id parameter"
    
    print("✅ Boredom check job is defined!")

def test_clawdbot_integration():
    print("\n🧪 Testing clawdbot integration...")
    
    with open(os.path.join(PROJECT_ROOT, "clawdbot.py"), "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "boredom_check" in content, "Should import boredom_check"
    assert 'name="projects"' in content, "/projects command should be defined"
    assert "start_portal" in content, "Should start portal"
    assert "NOSEY FRIEND MODE" in content, "Should have nosey friend rules"
    assert "boredom_engine.update_activity()" in content, "Should update boredom on activity"
    
    print("✅ Clawdbot integration complete!")

def test_nosey_rules():
    print("\n🧪 Testing nosey friend rules in prompt...")
    
    with open(os.path.join(PROJECT_ROOT, "clawdbot.py"), "r", encoding="utf-8") as f:
        content = f.read()
    
    # Key nosey rules
    assert "1-2 sharp follow-ups" in content, "Should limit questions"
    assert "Copy. Dropping it" in content, "Should respect 'not now'"
    assert "NEVER:" in content, "Should have never rules"
    assert "Snoop" in content, "Should prohibit snooping"
    
    print("✅ Nosey friend rules are in place!")

if __name__ == "__main__":
    test_boredom_engine_imports()
    test_project_ideas()
    test_boredom_detection()
    test_announcement_types()
    test_portal_imports()
    test_scheduler_job()
    test_clawdbot_integration()
    test_nosey_rules()
    
    print("\n🎉 All Boredom Engine & Creative Portal tests passed!")
