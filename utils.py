"""
Utility functions for Clawdbot.
"""
import re

def sanitize_for_discord(text: str) -> str:
    """
    Remove <thought> tags, raw JSON, code blocks, and command echoes.
    Ensures human-style output.
    """
    if not text: return ""
    
    # Remove thought blocks (non-greedy)
    text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL)
    
    # Remove standalone JSON tool calls or blobs
    # Be careful not to remove valid code blocks that happen to be JSON
    # We target tool call patterns specifically if possible, or large JSON blobs at end of message
    text = re.sub(r'\{\s*"name":\s*".*?"\s*,\s*"parameters":\s*\{.*?\}\s*\}', '', text, flags=re.DOTALL)
    
    # Remove Python code blocks that look like internal commands (import os, os.mkdir)
    # Only if they are bare (not in markdown blocks), but simpler to just target specific patterns
    text = re.sub(r'^import\s+os.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^from\s+\w+\s+import.*$', '', text, flags=re.MULTILINE)
    
    # Remove command echo lines
    text = re.sub(r'^(mkdir|cd|rm|del|copy|move)\s+.*$', '', text, flags=re.MULTILINE)
    
    # Remove absolute file paths (privacy/clutter)
    text = re.sub(r'[A-Z]:\\[^\n]*', '[PATH_REDACTED]', text)
    text = re.sub(r'/Users/[^\n]*', '[PATH_REDACTED]', text)
    
    # Collapse excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()
