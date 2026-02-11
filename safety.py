"""
Safety module — delegates to the consolidated sanitization layer.
Kept for backward compatibility with existing imports.
"""
from safety_layer.sanitize import (
    sanitize_outbound_text,
    enforce_allowlist_mentions,
)


def sanitize_for_discord(text: str) -> str:
    """Delegates to sanitize_outbound_text."""
    return sanitize_outbound_text(text)


def sanitize_output(text: str, is_admin_context: bool = False) -> str:
    """Delegates to sanitize_outbound_text."""
    return sanitize_outbound_text(text)


# Re-export so `import safety; safety.enforce_allowlist_mentions(...)` still works
__all__ = ["sanitize_for_discord", "sanitize_output", "enforce_allowlist_mentions"]
