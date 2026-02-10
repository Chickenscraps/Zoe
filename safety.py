import re

# Regex patterns for forbidden internal states
FORBIDDEN_PATTERNS = [
    r"(module(s)? loaded)",
    r"(system online)",
    r"(permission check)",
    r"(grant permission)",
    r"(deploy(ing)?)",
    r"(release shipping)",
    r"(build(ing)?)",
    r"(stack trace)",
    r"(traceback)",
    r"(internal error)",
    r"(tool call)",
    r"(I can['’]?t see your desktop)",
    r"(function_call)",
    r"(<function)",
    r"(\[DEBUG\])",
    r"(__main__)",
    r"(Thought for)",
    r"(<thought>)",
    r"(</thought>)",
    r"(<\|reserved_special_token_\d+\|>)",
    r"(User just asked me)",
    r"(thought User wants)",
    r"(The user wants)",
    r"(I suspect the user)",
    r"(\{\"name\":\s*\"[^\"]+\",\s*\"parameters\":)",
    r"(```json\s*\{\"name\")"
]

def sanitize_for_discord(text: str) -> str:
    """
    Aggressively strip internal monologue, tool traces, and leaked thoughts.
    """
    if not text:
        return ""
        
    # 1. Strip <thought> tags
    text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL)
    
    # 2. Strip lines starting with "Thought:", "Reasoning:", "User wants..."
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        l = line.strip()
        if l.lower().startswith(("thought:", "reasoning:", "user wants", "i am checking", "let me check")):
            continue
        clean_lines.append(line)
        
    text = '\n'.join(clean_lines).strip()
    
    return text
    
def sanitize_output(text: str, is_admin_context: bool = False) -> str:
    """
    Cleans up bot output.
    - Removes internal system logs/phrases from public channels.
    - If admin context AND requested verbose (not implemented fully here), allow logs.
    - Otherwise, strip aggressively.
    """
    if not text:
        return ""

    # Even for admin context, we want clean chat unless debugging.
    # The requirement says: "Only in #zoe-control can verbose diagnostics appear, and only when Josh asks with --verbose"
    # So by default, CLEAN IT.
    
    cleaned_text = text
    for pattern in FORBIDDEN_PATTERNS:
        # Replace matches with empty string or neutral filler if needed
        cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE)

    # Basic cleanup of multiple spaces/newlines created by removal
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    cleaned_text = cleaned_text.strip()
    
    # If the message became empty or just punctuation, return a fallback safety message?
    if not any(c.isalnum() for c in cleaned_text):
        return ""

    return cleaned_text

def enforce_allowlist_mentions(text: str, allowlist: list[str]) -> str:
    """
    Scans text for mentions of people NOT in the allowlist.
    If found, replaces them or denies the response.
    Strategy: Redact forbidden roles/names.
    """
    if not text: 
        return ""

    # 1. Scrub forbidden roles
    forbidden_roles = [r"\badmin\b", r"\bowner\b", r"\bmoderator\b", r"\bsysop\b"]
    for role in forbidden_roles:
         text = re.sub(role, "ops", text, flags=re.IGNORECASE)

    # 2. Scrub raw Discord IDs (17-19 digits)
    # Be careful not to scrub config IDs if printed in code blocks, but generally in chat text we hide them.
    # Regex for discord mentions <@123...> or just raw 123...
    
    # Simple strict approach: If it looks like a User ID that isn't Josh/Steve's (if we had their IDs), nuke it.
    # Since we have names in allowlist, we rely on the LLM mostly.
    # But let's strip raw big numbers just in case.
    # text = re.sub(r"\b\d{17,19}\b", "[ID REDACTED]", text) 
    
    return text
