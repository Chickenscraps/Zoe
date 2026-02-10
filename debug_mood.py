import os
import sys
import inspect

SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT PERSONA SKILL")
sys.path.insert(0, SKILL_DIR)

print(f"SKILL_DIR: {SKILL_DIR}")
print(f"sys.path: {sys.path}")

try:
    import mood_engine
    print(f"Attributes of module mood_engine: {dir(mood_engine)}")
    print(f"File of mood_engine: {mood_engine.__file__}")
    
    from mood_engine import mood_engine as me_instance
    print(f"Instance type: {type(me_instance)}")
    print(f"Instance dir: {dir(me_instance)}")
    
    if hasattr(me_instance, 'decay_mood'):
        print("✅ decay_mood exists!")
    else:
        print("❌ decay_mood MISSING!")
        
except Exception as e:
    print(f"Import failed: {e}")
