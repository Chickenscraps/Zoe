import os
import sys
import json

# Add skill dir to path
SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT PERSONA SKILL")
sys.path.append(SKILL_DIR)

try:
    from creative_engine import check_taste_gate, format_reveal, generate_three_paths_prompt
    print("✅ Successfully imported creative_engine")
except ImportError as e:
    print(f"❌ Failed to import creative_engine: {e}")
    sys.exit(1)

def verify_persona():
    try:
        with open(os.path.join(SKILL_DIR, "persona.json"), "r") as f:
            data = json.load(f)
            if data.get("impress_mode", {}).get("enabled"):
                print("✅ Impress Mode enabled in persona.json")
            else:
                print("❌ Impress Mode NOT enabled in persona.json")
                
            banned = data.get("impress_mode", {}).get("banned_phrases", [])
            if "As an AI language model" in banned:
                print("✅ Banned phrases present")
            else:
                print("❌ Banned phrases missing")
    except Exception as e:
        print(f"❌ Error reading persona.json: {e}")

def verify_taste_gate():
    bad_text = "I hope this helps! 🚀🚀🚀 As an AI, I suggest..."
    result = check_taste_gate(bad_text)
    if not result["passed"]:
        print(f"✅ Taste Gate caught bad text: {result['violations']}")
    else:
        print(f"❌ Taste Gate FAILED to catch bad text: {bad_text}")

    good_text = "Here is the spicy upgrade. Let's do it."
    result = check_taste_gate(good_text)
    if result["passed"]:
        print("✅ Taste Gate allowed good text")
    else:
        print(f"❌ Taste Gate blocked good text: {result['violations']}")

def verify_reveal():
    output = format_reveal(
        "Project X",
        "It changes everything.",
        ["Step 1", "Step 2"],
        "link_to_file",
        "Phase 2"
    )
    if "### ✨ Project X" in output and "**Demo Plan:**" in output:
        print("✅ Reveal format looks correct")
    else:
        print("❌ Reveal format incorrect")

if __name__ == "__main__":
    print("--- Verifying Impress Mode ---")
    verify_persona()
    verify_taste_gate()
    verify_reveal()
    print("\n--- Done ---")
