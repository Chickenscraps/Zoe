"""
AI Coder Module
Generates code patches and diffs using the Model Router.
"""
import os
import re
from typing import Optional, List, Dict
from model_router import router

# =============================================================================
# Configuration
# =============================================================================

# Policy checks (kept from original)
from pathlib import Path
import json
import fnmatch

POLICY_PATH = Path(__file__).parent / "zoe_policy.json"

def load_policy() -> dict:
    try:
        with open(POLICY_PATH, "r") as f:
            return json.load(f)
    except:
        return {"allowed_write_paths": [], "denied_patterns": []}

def check_path_policy(file_path: str) -> tuple[bool, str]:
    policy = load_policy()
    path_str = str(Path(file_path).resolve())
    for pattern in policy.get("denied_patterns", []):
        if fnmatch.fnmatch(path_str, pattern):
            return False, f"Path denied: {pattern}"
    return True, "Allowed"

# =============================================================================
# Core Logic
# =============================================================================

async def ask_coder(task: str, context: str = "", model: Optional[str] = None) -> str:
    """
    Ask the AI coder to generate a solution/patch.
    Delegates to model_router for backend selection.
    """
    system_prompt = (
        "You are an expert AI software engineer (Zoe).\n"
        "Your goal is to write clean, efficient, and error-free code.\n"
        "Return ONLY the code block or the specific requested output.\n"
        "Do not include conversational filler unless requested."
    )
    
    messages = [
        {"role": "user", "content": f"Context:\n{context}\n\nTask: {task}"}
    ]
    
    # Use router global instance
    try:
        from model_router import model_router
        return await model_router.chat(messages, system=system_prompt, model=model)
    except Exception as e:
        print(f"Error in ask_coder: {e}")
        return f"Error: {e}"
__all__ = ["ask_coder", "check_path_policy"]
