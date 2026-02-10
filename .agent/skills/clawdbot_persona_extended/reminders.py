
import time
import os
import json
from datetime import datetime, timedelta
import sys

# Import Journal Logger
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.append(SKILL_DIR)

try:
    from journal_logger import log_event, get_log_file
except ImportError:
    def log_event(*args, **kwargs): pass
    def get_log_file(mode): return "journal_organize.jsonl"

REMINDER_INTERVAL = 2 * 3600 # 2 hours
FLOW_WINDOW = 15 * 60 # 15 minutes
DELAY_INCREMENT = 15 * 60 # 15 minutes

def is_in_flow():
    """
    Checks if there were transcription events in the last FLOW_WINDOW seconds.
    """
    log_file = get_log_file("organize")
    if not os.path.exists(log_file):
        return False
    
    now = datetime.utcnow()
    flow_threshold = now - timedelta(seconds=FLOW_WINDOW)
    
    try:
        # Read last few lines (naive approach)
        with open(log_file, "r") as f:
            lines = f.readlines()[-20:] # Check last 20 entries
            for line in reversed(lines):
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts > flow_threshold and entry.get("event", "").startswith("voice."):
                    return True
    except Exception as e:
        print(f"Error checking flow: {e}")
    
    return False

def main():
    print("💧 Reminder Service Active (Water + Stretch every 2h).")
    last_reminder_time = time.time()
    
    while True:
        current_time = time.time()
        elapsed = current_time - last_reminder_time
        
        if elapsed >= REMINDER_INTERVAL:
            if is_in_flow():
                print("🧘 User in flow. Delaying reminder by 15 mins...")
                time.sleep(DELAY_INCREMENT)
                continue
            
            print("🔔 Reminder: Time to drink water and stretch!")
            log_event("REMINDER", "Water + Stretch reminder triggered", mode="organize")
            # In a real setup, we might trigger a TTS or a desktop notification here
            
            last_reminder_time = time.time()
        
        time.sleep(60) # Check every minute

if __name__ == "__main__":
    main()
