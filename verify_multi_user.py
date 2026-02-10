import sys
import os
import json
from datetime import datetime

# Add skill dir
SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT PERSONA SKILL")
sys.path.insert(0, SKILL_DIR)

from memory_store import memory, get_memory_context
from relationship_manager import relationship_manager

def test_multi_user_memory():
    print("🧪 Testing Multi-User Memory Segregation...")
    
    # IDs
    JOSH_ID = "292890243852664855"
    BEN_ID = "490911982984101901"
    
    # 1. Log Activity for Josh
    print(f"\n[1] Logging activity for Josh ({JOSH_ID})...")
    memory.log_activity("coding", 60, {"project": "Clawdbot"}, user_id=JOSH_ID)
    
    # 2. Log Activity for Ben
    print(f"\n[2] Logging activity for Ben ({BEN_ID})...")
    memory.log_activity("gaming", 120, {"game": "Valheim"}, user_id=BEN_ID)
    
    # 3. Verify Context Segregation
    print("\n[3] Verifying Context Segregation...")
    
    josh_ctx = get_memory_context(JOSH_ID)
    ben_ctx = get_memory_context(BEN_ID)
    
    print(f"\nJosh Context Preview:\n{josh_ctx}")
    print(f"\nBen Context Preview:\n{ben_ctx}")
    
    if "Valheim" in josh_ctx:
        print("❌ FAILED: Josh sees Ben's gaming activity!")
    elif "Clawdbot" not in josh_ctx:
        print("❌ FAILED: Josh cannot see his own activity!")
    else:
        print("✅ SUCCESS: Josh's memory is isolated.")
        
    if "Clawdbot" in ben_ctx:
        print("❌ FAILED: Ben sees Josh's coding activity!")
    elif "Valheim" not in ben_ctx:
        print("❌ FAILED: Ben cannot see his own activity!")
    else:
        print("✅ SUCCESS: Ben's memory is isolated.")

    # 4. Verify Relationship Context
    print("\n[4] Verifying Relationship Context...")
    josh_rel = relationship_manager.get_relationship_context(JOSH_ID)
    ben_rel = relationship_manager.get_relationship_context(BEN_ID)
    
    print(f"Josh Relationship: {josh_rel.strip()}")
    print(f"Ben Relationship: {ben_rel.strip()}")
    
    if "Josh" in josh_rel and "Ben" in ben_rel:
        print("✅ SUCCESS: Relationship context is correct.")
    else:
        print("❌ FAILED: Relationship context mismatch.")

if __name__ == "__main__":
    test_multi_user_memory()
