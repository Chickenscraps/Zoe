"""
Prompt Loader — Composes Zoe's system prompt from /prompts/ markdown files.

Usage:
    from prompt_loader import build_system_prompt

    prompt = build_system_prompt(
        config=ZOECONFIG,
        room_context_json=room_ctx,
        goals="...",
        memories=["..."],
        is_startup=True
    )
"""
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

# Cache loaded prompt files (invalidated on file mtime change)
_prompt_cache: Dict[str, tuple] = {}  # filename -> (mtime, content)


def _load_prompt_file(filename: str) -> str:
    """Load a prompt file from /prompts/ with mtime-based caching."""
    filepath = os.path.join(PROMPTS_DIR, filename)

    if not os.path.exists(filepath):
        logger.warning(f"Prompt file not found: {filepath}")
        return ""

    mtime = os.path.getmtime(filepath)

    if filename in _prompt_cache:
        cached_mtime, cached_content = _prompt_cache[filename]
        if cached_mtime == mtime:
            return cached_content

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    _prompt_cache[filename] = (mtime, content)
    logger.info(f"Loaded prompt: {filename} ({len(content)} chars)")
    return content


def build_system_prompt(
    config: Dict[str, Any],
    room_context_json: str = "",
    goals: str = "",
    memories: Optional[List[str]] = None,
    is_startup: bool = False,
    user_id: Optional[str] = None,
) -> str:
    """
    Compose the full system prompt from file-based prompt segments.

    Args:
        config: The ZOECONFIG dict (from config.yaml)
        room_context_json: JSON string from RoomContextBuilder.build()
        goals: Current goals/obsessions string
        memories: List of recalled memory strings
        is_startup: Whether this is the first message in a channel session
        user_id: Discord user ID of the message author

    Returns:
        Complete system prompt string ready for LLM.
    """
    parts = []

    # 1. System rules (hard rules, model policy, safety)
    parts.append(_load_prompt_file("system.md"))

    # 2. Persona (voice, behavior, idle mode)
    parts.append(_load_prompt_file("persona.md"))

    # 3. Trading policy
    parts.append(_load_prompt_file("trading_policy.md"))

    # 4. Dynamic context header
    now = datetime.now()
    parts.append(f"""
## CURRENT SESSION
- Date: {now.strftime("%A, %B %d, %Y")}
- Time: {now.strftime("%H:%M")} (local)
- Admin ID: {config.get('admin', {}).get('admin_user_ids', ['292890243852664855'])[0]}
""")

    # 5. Persona config overrides
    persona_cfg = config.get("persona", {})
    allowlist = persona_cfg.get("mention_allowlist", ["Josh", "Steve"])
    boundary_words = persona_cfg.get("boundary_words", ["stop", "no"])
    flirt_on = persona_cfg.get("flirt_mode", False)

    parts.append(f"""
## IDENTITY GUARD
- PEOPLE: You ONLY know/discuss {allowlist}. Refuse others politely.
- FLIRT MODE: {'ON' if flirt_on else 'OFF'}. Be playful if on, but respect boundaries.
- BOUNDARY WORDS: {boundary_words} — if user says any of these, stop immediately.
""")

    # 6. Goals
    if goals:
        parts.append(f"\n## CURRENT OBSESSIONS (Goals)\n{goals}")

    # 7. Memories
    if memories:
        parts.append("\n## RECALLED MEMORIES\n" + "\n".join(f"- {m}" for m in memories))

    # 8. ROOM_CONTEXT (always last before instructions)
    if room_context_json:
        parts.append(f"\n## ROOM_CONTEXT (last 10 messages, sanitized)\n{room_context_json}")

    # 9. Startup ritual tag
    if is_startup:
        parts.append("\n[STARTUP RITUAL] — Read ROOM_CONTEXT and craft a reconnect message. Prove you read the room. 2-4 lines max.")

    return "\n\n".join(part for part in parts if part.strip())
