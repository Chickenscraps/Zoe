"""
Verification script for AGI Refinement & Persona Integration
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

def test_persona_loader():
    print("\n🧪 Testing persona_loader imports...")
    from persona_loader import (
        get_user_persona, get_user_context, get_voice_mode_instructions,
        calculate_mood_tone, get_time_aware_greeting, ZOE_CATCHPHRASES,
        GROUP_INSIDE_JOKES, VOICE_MODES, get_random_catchphrase
    )
    
    print("✅ All imports successful!")

def test_user_personas():
    print("\n🧪 Testing user persona loading...")
    from persona_loader import get_user_persona, get_user_name, USER_ID_MAP
    
    # Test Josh's persona
    josh_persona = get_user_persona("292890243852664855")
    assert josh_persona is not None, "Josh's persona should load"
    assert josh_persona.get("name") == "Josh"
    assert "stocks" in josh_persona.get("interests", [])
    
    # Test Ben's persona
    ben_persona = get_user_persona("490911982984101901")
    assert ben_persona is not None, "Ben's persona should load"
    assert "Keep the stonks outta here!" in ben_persona.get("common_phrases", [])
    
    print(f"   Josh: {josh_persona.get('message_count')} messages, interests: {josh_persona.get('interests', [])[:3]}")
    print(f"   Ben: {ben_persona.get('message_count')} messages, phrases: {ben_persona.get('common_phrases', [])[:2]}")
    print("✅ User personas loaded correctly!")

def test_user_context():
    print("\n🧪 Testing user context generation...")
    from persona_loader import get_user_context
    
    context = get_user_context("292890243852664855")  # Josh
    
    assert "Josh" in context, "Context should contain user name"
    assert "stocks" in context.lower() or "gaming" in context.lower(), "Context should have interests"
    assert "Inside Jokes" in context, "Context should mention inside jokes"
    
    print(f"   Context length: {len(context)} chars")
    print("✅ User context generation works!")

def test_voice_modes():
    print("\n🧪 Testing voice modes...")
    from persona_loader import VOICE_MODES, get_voice_mode_instructions
    
    assert len(VOICE_MODES) == 4, "Should have 4 voice modes"
    assert "playful" in VOICE_MODES
    assert "focused" in VOICE_MODES
    assert "calm" in VOICE_MODES
    assert "silent" in VOICE_MODES
    
    playful_inst = get_voice_mode_instructions("playful")
    assert "cheeky" in playful_inst.lower(), "Playful mode should mention cheeky"
    
    focused_inst = get_voice_mode_instructions("focused")
    assert "brief" in focused_inst.lower(), "Focused mode should mention brief"
    
    print("✅ Voice modes configured correctly!")

def test_mood_tone():
    print("\n🧪 Testing dynamic mood tone...")
    from persona_loader import calculate_mood_tone
    
    # High valence + romance = extra playful
    high_romance = calculate_mood_tone(0.8, True)
    assert "playful" in high_romance.lower(), "High mood + romance should be extra playful"
    
    # Low valence = professional
    low_mood = calculate_mood_tone(-0.5, False)
    assert "low" in low_mood.lower() or "professional" in low_mood.lower(), "Low mood should be professional"
    
    print("✅ Dynamic mood tone works!")

def test_catchphrases():
    print("\n🧪 Testing catchphrases and inside jokes...")
    from persona_loader import ZOE_CATCHPHRASES, GROUP_INSIDE_JOKES
    
    assert len(ZOE_CATCHPHRASES) >= 5, "Should have multiple catchphrases"
    assert "Vibe check?" in ZOE_CATCHPHRASES
    
    assert len(GROUP_INSIDE_JOKES) >= 5, "Should have multiple inside jokes"
    
    # Check joke format
    for joke, triggers in GROUP_INSIDE_JOKES:
        assert isinstance(joke, str), "Joke should be string"
        assert isinstance(triggers, list), "Triggers should be list"
    
    print(f"   {len(ZOE_CATCHPHRASES)} catchphrases, {len(GROUP_INSIDE_JOKES)} inside jokes")
    print("✅ Catchphrases and inside jokes configured!")

def test_mode_command_exists():
    print("\n🧪 Testing /mode command definition...")
    
    with open(os.path.join(PROJECT_ROOT, "clawdbot.py"), "r", encoding="utf-8") as f:
        content = f.read()
    
    assert 'name="mode"' in content, "/mode command should be defined"
    assert "voice_mode" in content, "voice_mode should be used"
    assert "VOICE_MODES" in content, "VOICE_MODES import should exist"
    
    print("✅ /mode command is defined!")

def test_system_prompt_integration():
    print("\n🧪 Testing system prompt has persona integration...")
    
    with open(os.path.join(PROJECT_ROOT, "clawdbot.py"), "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "get_user_context" in content, "Should import get_user_context"
    assert "get_voice_mode_instructions" in content, "Should import voice mode instructions"
    assert "INSIDE JOKES" in content, "System prompt should mention inside jokes"
    assert "CATCHPHRASES" in content, "System prompt should mention catchphrases"
    
    print("✅ System prompt integrates persona data!")

if __name__ == "__main__":
    test_persona_loader()
    test_user_personas()
    test_user_context()
    test_voice_modes()
    test_mood_tone()
    test_catchphrases()
    test_mode_command_exists()
    test_system_prompt_integration()
    
    print("\n🎉 All AGI Refinement tests passed!")
