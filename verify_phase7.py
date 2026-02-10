
import sys
import os
import json
import time

SKILL_DIR = os.path.join(os.getcwd(), "AGENT PERSONA SKILL")
sys.path.insert(0, SKILL_DIR)

def verify_workstreams():
    print("\n--- Verifying Workstream Manager ---")
    try:
        from workstream_manager import workstream_manager
        active = workstream_manager.get_all_active()
        print(f"Active workstreams: {list(active.keys())}")
        if "PRIMARY" in active:
            print("✅ Primary workstream found.")
        else:
            print("❌ Primary workstream missing.")
    except Exception as e:
        print(f"❌ Workstream Manager failed: {e}")

def verify_nudge_engine():
    print("\n--- Verifying Nudge Engine ---")
    try:
        from nudge_engine import nudge_engine
        print("Executing tick...")
        result = nudge_engine.tick()
        print(f"Tick Result: {result}")
        if result.startswith("["):
            print("✅ Tick executed successfully.")
        else:
            print("❌ Tick result format unexpected.")
    except Exception as e:
        print(f"❌ Nudge Engine failed: {e}")

def verify_idea_vault():
    print("\n--- Verifying Idea Vault ---")
    try:
        from idea_vault import idea_vault
        idea_vault.add_idea("Verification Idea", "Testing script", "High")
        ideas = idea_vault.get_ideas()
        found = any(i['title'] == "Verification Idea" for i in ideas)
        if found:
            print(f"✅ Idea added and found. Total ideas: {len(ideas)}")
        else:
            print("❌ Idea not found.")
    except Exception as e:
        print(f"❌ Idea Vault failed: {e}")

def verify_journal():
    print("\n--- Verifying Project Journal ---")
    try:
        from project_journal import ProjectJournal
        pj = ProjectJournal("test-project-phase7")
        pj.update_section("Next Actions", "- [ ] Verify Phase 7")
        actions = pj.get_next_actions()
        if "Verify Phase 7" in actions:
            print("✅ Journal created and updated.")
        else:
            print("❌ Journal update failed.")
    except Exception as e:
        print(f"❌ Project Journal failed: {e}")

if __name__ == "__main__":
    verify_workstreams()
    verify_idea_vault()
    verify_journal()
    verify_nudge_engine()
