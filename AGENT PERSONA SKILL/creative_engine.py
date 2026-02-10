"""
Creative Engine for Clawdbot
Implements "Impress Mode" logic, taste gates, and creative scoring.
"""
import os
import json
import random
from typing import Dict, List, Optional

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

# Banned phrases that kill the vibe
BANNED_PHRASES = [
    "as an ai",
    "i apologize",
    "i hope this helps",
    "i am just a tool",
    "please let me know if",
    "i might be wrong but",
    "let's dive in",
    "in summary",
    "it's important to note"
]

# Cringe patterns
CRINGE_TOKENS = [
    "🚀🚀🚀", "🔥🔥🔥", "💯💯💯", # Emoji spam
    "hustle", "grindset", "10x engineer", # Corny slang
]

def load_persona() -> Dict:
    try:
        path = os.path.join(SKILL_DIR, "persona.json")
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}

def check_taste_gate(text: str) -> Dict[str, any]:
    """
    Analyzes text for 'taste' violations.
    Returns {passed: bool, reason: str, improvements: list}
    """
    text_lower = text.lower()
    violations = []
    
    # Check banned phrases
    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            violations.append(f"Contains banned humble filler: '{phrase}'")
            
    # Check cringe tokens
    for token in CRINGE_TOKENS:
        if token in text_lower:
            violations.append(f"Contains cringe token: '{token}'")
    
    # Check emoji density (simple heuristic)
    emoji_count = sum(1 for char in text if ord(char) > 0x1F000)
    if len(text) > 0 and (emoji_count / len(text)) > 0.05:
        violations.append("Too many emojis (keep it clean)")
        
    return {
        "passed": len(violations) == 0,
        "violations": violations
    }

def score_creativity(text: str) -> Dict[str, float]:
    """
    Heuristic scoring of creativity (internal use).
    Real scoring would need an LLM, but this is a rough proxy for length/complexity.
    """
    # Placeholder: Length and structure analysis
    score = {
        "novelty": 0.5,
        "usefulness": 0.5,
        "wow_factor": 0.1
    }
    
    if "spicy" in text.lower() or "wildcard" in text.lower():
        score["novelty"] += 0.3
        
    if "demo" in text.lower() or "steps" in text.lower():
        score["usefulness"] += 0.3
        
    return score

def format_reveal(title: str, why: str, demo_steps: List[str], artifact: str = None, next_upgrade: str = None) -> str:
    """
    Formats a polished 'Showcase Reveal' block.
    """
    demo_str = "\n".join([f"{i+1}. {step}" for i, step in enumerate(demo_steps)])
    
    parts = [
        f"### ✨ {title}",
        f"**Why it matters:** {why}",
        "",
        "**Demo Plan:**",
        demo_str
    ]
    
    if artifact:
        parts.append(f"\n**Artifact:** {artifact}")
        
    if next_upgrade:
        parts.append(f"\n**Next Upgrade:** {next_upgrade}")
        
    return "\n".join(parts)

def generate_three_paths_prompt() -> str:
    """
    Returns the system prompt injection for Three Paths.
    """
    return """
IMPRESS MODE ACTIVE.
You must assume the persona of a bold, tasteful ops cofounder.
Thinking Process:
1. Standard Solution: The safe path.
2. Spicy Upgrade: The high-leverage path.
3. Wildcard: The unexpected path.

Output Format:
Present your recommendation decively. 
"We're doing [Option]. Here's why."
If relevant, show the Spicy Upgrade as a "Stretch Goal".
Avoid humble filler.
"""

def suggest_visual(idea: str) -> str:
    """
    Generate a visual prompt for an idea.
    Currently returns a template, can be improved with LLM.
    """
    templates = [
        f"A cybernetic visualization of {idea}, neon lights, 8k",
        f"Oil painting of {idea}, dramatic lighting, classical style",
        f"Minimalist vector art representing {idea}, clean lines",
        f"3D render of {idea}, octane render, unreal engine",
        f"Surrealist interpretation of {idea}, dali style, melting clocks",
        f"Abstract data stream of {idea}, matrix code, glowing green"
    ]
    return random.choice(templates)


if __name__ == "__main__":
    # Test
    print(check_taste_gate("I hope this helps! 🚀🚀🚀"))
    print(format_reveal(
        "Impress Mode",
        "Because boring agents get deleted.",
        ["Generate 3 paths", "Filter cringe", "Ship it"],
        "creative_engine.py",
        "Add LLM-based scoring"
    ))
