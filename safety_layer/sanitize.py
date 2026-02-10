import re

def sanitize_inbound_text(text: str) -> str:
    """
    Sanitize inbound Discord messages for ROOM_CONTEXT.
    - strip mentions (<@...> → @user)
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

def sanitize_outbound_text(text: str) -> str:
    """
    STRICT outbound sanitizer for Zoe's LLM responses.
    Removes forbidden internal patterns, thoughts, and technical leaks.
    """
    if not text:
        return "Got it. Give me one sec—what’s the goal here?"

    # Forbidden patterns
    forbidden = [
        r'(?i)\bthought for\b.*',
        r'(?i)\breasoned\b.*',
        r'(?i)\bprogress updates?\b.*',
        r'(?i)\bpermission check\b.*',
        r'(?i)\buser wants me to\b.*',
        r'(?i)stack trace|traceback|exception|error in tick',
        r'(?s)```.*?```', # Code fences
        r'(?s)\{[\s\S]*"path"[\s\S]*\}' # JSON blobs with "path"
    ]

    for pattern in forbidden:
        text = re.sub(pattern, '', text)

    # Collapse >2 blank lines to max 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Trim final whitespace
    text = text.strip()

    # Fallback if empty
    if not text:
        return "Got it. Give me one sec—what’s the goal here?"

    # Cap to Discord limit (safely)
    return text[:1800]
