"""
Sanitization Layer for Zoe
- Inbound: clean Discord messages for ROOM_CONTEXT
- Outbound: strip ALL internal traces before posting to Discord
"""
import re


# ─── Inbound Sanitization (Discord -> ROOM_CONTEXT) ───

def sanitize_inbound_text(text: str) -> str:
    """
    Sanitize inbound Discord messages for ROOM_CONTEXT.
    - strip mentions (<@...> -> @user)
    - replace links with [link]
    - flatten newlines
    - cap each message to 240 chars
    """
    # Mentions
    text = re.sub(r'<@!?[0-9]+>', '@user', text)
    # Role mentions
    text = re.sub(r'<@&[0-9]+>', '@role', text)
    # Channel mentions
    text = re.sub(r'<#[0-9]+>', '#channel', text)
    # Links
    text = re.sub(r'https?://[^\s]+', '[link]', text)
    # Flatten newlines
    text = text.replace('\n', ' ').replace('\r', ' ')
    # Multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    # Cap length
    return text[:240]


# ─── Outbound Sanitization (LLM Response -> Discord) ───

# Patterns that MUST be stripped from any outbound message.
# These catch chain-of-thought leaks, tool traces, and bot artifacts.
_OUTBOUND_FORBIDDEN_RAW = [
    # Chain-of-thought / reasoning leaks
    r'(?im)^(?:thought|thinking|reasoning|reflection|analysis):?\s.*$',
    r'(?i)\bthought for \d+',
    r'(?i)\breasoned for \d+',
    r'(?i)\bprogress update:?\b.*',
    # Internal monologue patterns (include optional leading words)
    r'(?i)(?:the\s+)?user wants me to\b.*',
    r'(?i)(?:the\s+)?user wants\b.*',
    r'(?i)(?:the\s+)?user just asked me\b.*',
    r'(?i)\bi suspect the user\b.*',
    r'(?i)\blet me (?:check|think|analyze)\b.*',
    r'(?i)\bi am checking\b.*',
    # System / tool traces
    r'(?i)\bpermission check\b.*',
    r'(?i)\bmodules? loaded\b.*',
    r'(?i)\bsystem online\b.*',
    r'(?i)\bgrant permission\b.*',
    r'(?i)\btool call\b.*',
    r'(?i)\bfunction_call\b.*',
    r'(?i)\bstack trace\b.*',
    r'(?i)\btraceback\b.*',
    r'(?i)\binternal error\b.*',
    r'(?i)\berror in tick\b.*',
    # XML-style tags
    r'<thought>.*?</thought>',
    r'</?thought>',
    r'<function\b[^>]*>',
    r'<\|reserved_special_token_\d+\|>',
    # Raw JSON tool call structures
    r'\{"name":\s*"[^"]+",\s*"parameters":.*?\}',
    # Debug markers
    r'\[DEBUG\].*',
    r'__main__.*',
]

# Pre-compile for performance.
# Do NOT use re.DOTALL — we want .* to stop at line boundaries
# so single-line artifacts don't consume remaining text.
# The <thought>...</thought> multiline stripping is handled separately above.
_OUTBOUND_PATTERNS = [re.compile(p) for p in _OUTBOUND_FORBIDDEN_RAW]


def sanitize_outbound_text(text: str) -> str:
    """
    STRICT outbound sanitizer for Zoe's LLM responses.
    Removes forbidden internal patterns, thoughts, and technical leaks.
    Returns clean text ready for Discord, or empty string if nothing remains.
    """
    if not text or not text.strip():
        return ""

    # 1. Strip <thought>...</thought> blocks (multiline)
    text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL)

    # 2. Apply all forbidden patterns
    for pattern in _OUTBOUND_PATTERNS:
        text = pattern.sub('', text)

    # 3. Strip lines that are pure system artifacts
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            clean_lines.append('')
            continue
        # Skip very short separator lines
        if stripped.startswith(('>>>', '---', '===')) and len(stripped) < 10:
            continue
        clean_lines.append(line)

    text = '\n'.join(clean_lines)

    # 4. Collapse excessive blank lines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 5. Trim
    text = text.strip()

    # 6. If nothing meaningful remains, return empty
    if not text or not any(c.isalnum() for c in text):
        return ""

    # 7. Cap to Discord-safe length
    if len(text) > 1800:
        text = text[:1797] + "..."

    return text


def enforce_allowlist_mentions(text: str, allowlist: list) -> str:
    """
    Scrub forbidden role names and raw Discord IDs from outbound text.
    """
    if not text:
        return ""

    # Scrub forbidden role keywords
    forbidden_roles = [r'\badmin\b', r'\bowner\b', r'\bmoderator\b', r'\bsysop\b']
    for role in forbidden_roles:
        text = re.sub(role, 'ops', text, flags=re.IGNORECASE)

    # Scrub raw Discord IDs (17-19 digit numbers)
    text = re.sub(r'(?<!\d)\d{17,19}(?!\d)', '[redacted-id]', text)

    return text
