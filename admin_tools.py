import secrets
import time
import logging

# Simple in-memory store for pending confirmations
# Structure: { nonce: { "action": str, "args": list, "user_id": int, "timestamp": float } }
pending_confirmations = {}

CONFIRMATION_TIMEOUT = 120  # 2 minutes

def execute_admin_command(bot, command: str, args: list, user_id: int, channel_id: int, is_admin_channel: bool):
    """
    Parses and routes admin commands.
    Returns a response string (message to user).
    """
    cmd = command.lower()

    if cmd == "confirm":
        if not args:
            return "Usage: `!zoe confirm <token>`"
        nonce = args[0]
        return process_confirmation(bot, nonce, user_id)

    if cmd == "run":
        # Shell command execution
        cmd_line = " ".join(args)
        if is_destructive(cmd_line):
           return request_confirmation("run_shell", [cmd_line], user_id)
        
        return run_shell(cmd_line)

    if cmd == "file":
        # !zoe file read <path>
        if not args:
            return "Usage: `!zoe file [read|write|list] <path> ...`"
        subcmd = args[0].lower()
        if subcmd == "read":
             path = args[1] if len(args) > 1 else ""
             return read_file(path)
        # Add write/list logic...
        
    return f"Unknown admin command: {cmd}"

def is_destructive(cmd_line: str) -> bool:
    """Simple heuristic for dangerous commands."""
    dangerous = ["rm ", "del ", "format ", "mkfs", "dd ", ">", "mv "]
    return any(d in cmd_line for d in dangerous)

def request_confirmation(action_type: str, args: list, user_id: int) -> str:
    """Generates a nonce and stores the pending action."""
    nonce = secrets.token_hex(4) # e.g. "a1b2c3d4"
    pending_confirmations[nonce] = {
        "action": action_type,
        "args": args,
        "user_id": user_id,
        "timestamp": time.time()
    }
    return f"⚠️ **Destructive Action Detected**\nConfirm with: `!zoe confirm {nonce}`\n(Expires in 2 mins)"

def process_confirmation(bot, nonce: str, user_id: int) -> str:
    """Validates nonce and executes the stored action."""
    record = pending_confirmations.get(nonce)
    
    if not record:
        return "❌ Invalid or expired confirmation token."
        
    if record["user_id"] != user_id:
        return "❌ That confirmation is not for you."
        
    if time.time() - record["timestamp"] > CONFIRMATION_TIMEOUT:
        del pending_confirmations[nonce]
        return "❌ Confirmation expired."
        
    # Execute
    action = record["action"]
    args = record["args"]
    
    # Cleanup
    del pending_confirmations[nonce]
    
    if action == "run_shell":
        return run_shell(args[0])
        
    return "Action confirmed but handler missing."

def run_shell(cmd_line: str) -> str:
    import subprocess
    try:
        # TIMEOUT added for safety
        result = subprocess.run(cmd_line, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout or result.stderr
        return f"```\n{output[:1900]}\n```" # Discord limit
    except Exception as e:
        return f"Error: {e}"

def read_file(path: str) -> str:
    import os
    if not os.path.exists(path):
        return "File not found."
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"```\n{content[:1900]}\n```"
    except Exception as e:
        return f"Error reading file: {e}"
