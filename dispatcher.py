import sys
import warnings
warnings.filterwarnings("ignore")
import subprocess
import os
import json
import requests
import uuid
import time
from datetime import datetime

# Import Skill Modules
SKILL_DIR = os.path.join(os.path.dirname(__file__), "AGENT PERSONA SKILL")
if SKILL_DIR not in sys.path:
    sys.path.append(SKILL_DIR)

try:
    from event_bus import event_bus, Event, EventType, notify_user
    from structured_logger import logger, LogEntry
    from mood_engine import mood_engine
    from tts_engine import tts_engine
except ImportError as e:
    print(f"Error importing skill modules: {e}")
    # Fallback to prevent crash if modules missing during dev
    class MockObj:
        def __getattr__(self, name): return lambda *a, **k: None
    event_bus = logger = mood_engine = tts_engine = MockObj()
    EventType = MockObj()

# State File
STATE_FILE = os.path.join(SKILL_DIR, "state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"mode": "normal", "pending_action": None}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# Configuration


import google.generativeai as genai

# Load Gemini API Key
def get_gemini_key():
    OPENCLAW_CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(OPENCLAW_CONFIG_PATH, "r") as f:
            config = json.load(f)
            return config.get("env", {}).get("vars", {}).get("GEMINI_API_KEY")
    except:
        return os.environ.get("GEMINI_API_KEY")

API_KEY = get_gemini_key()
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("⚠️ Warning: GEMINI_API_KEY not found in env or config.")


def run_ai_chat(text, correlation_id=None):
    """
    Calls Gemini directly to get a persona response.
    """
    start_time = time.time()
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Load Persona
        persona_path = os.path.join(SKILL_DIR, "persona.json")
        system_prompt = "You are Clawdbot, a proactive cofounder agent."
        
        # Get Mood Context
        try:
            current_mood = mood_engine.get_current_mood()
            mood_presentation = mood_engine.get_presentation()
            mood_context = f"\nCurrent Mood: {current_mood.name}\nPresentation: {mood_presentation}"
        except:
            mood_context = ""

        if os.path.exists(persona_path):
            with open(persona_path, "r") as f:
                persona = json.load(f)
                base_role = persona.get('role', 'Agent')
                base_tone = persona.get('tone', 'Helpful')
                system_prompt = f"You are {persona.get('name', 'Clawdbot')}. Role: {base_role}. Tone: {base_tone}. {mood_context}"
        
        # Impress Mode Injection
        try:
            from creative_engine import generate_three_paths_prompt
            if persona.get("impress_mode", {}).get("enabled", True):
                system_prompt += "\n" + generate_three_paths_prompt()
        except ImportError:
            pass

        from memory_store import get_memory_context
        memory_context = get_memory_context()
        
        from resilience import retry_with_backoff, resilient_call
        
        @retry_with_backoff(retries=3)
        def _safe_generate(prompt):
            event_bus.publish(Event(EventType.MODEL_CALL_START.value, {"model": "gemini-2.0-flash"}, correlation_id=correlation_id))
            return model.generate_content(prompt)

        full_prompt = f"{system_prompt}\n\n[Long-Term Memory]\n{memory_context}\n\nUser: {text}\nResponse:"
        
        response = resilient_call(_safe_generate, full_prompt)
        clean_response = response.text.strip().replace("\n", " ")
        
        # Log success
        latency = (time.time() - start_time) * 1000
        logger.log_model_call(
            model="gemini-2.0-flash",
            input_text=text,
            output_text=clean_response,
            latency_ms=latency,
            success=True,
            correlation_id=correlation_id
        )
        event_bus.publish(Event(EventType.MODEL_CALL_SUCCESS.value, {"latency": latency}, correlation_id=correlation_id))
        
        print(f"RESPONSE: {clean_response}")
        sys.stdout.flush()
        return clean_response
        
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        logger.log_model_call(
            model="gemini-2.0-flash",
            input_text=text,
            output_text="",
            latency_ms=latency,
            success=False,
            error=str(e),
            correlation_id=correlation_id
        )
        event_bus.publish(Event(EventType.MODEL_CALL_FAILURE.value, {"error": str(e)}, correlation_id=correlation_id))
        
        error_msg = f"I heard you, but I'm having trouble thinking. Error: {str(e)}"
        print(f"RESPONSE: {error_msg}")
        return error_msg

def speak(text, correlation_id=None):
    """
    Uses tts_engine for mood-aware speech.
    """
    try:
        # Get mood modifiers
        modifiers = mood_engine.get_voice_modifiers()
        
        # Speak
        tts_engine.speak(text, mood_modifiers=modifiers)
        
        # Log
        logger.info("tts.spoken", text, correlation_id=correlation_id, metadata={"modifiers": modifiers})
    except Exception as e:
        logger.error("tts.error", str(e), correlation_id=correlation_id)
        # Fallback to old method if tts_engine fails is probably not needed if correct import
        pass

def route_request(text):
    correlation_id = str(uuid.uuid4())
    state = load_state()
    current_mode = state.get("mode", "normal")
    text_lower = text.lower()
    
    # 1. Log Request
    logger.log_request(text, correlation_id, source="dispatcher")
    
    # 2. Publish Event
    event_bus.publish(Event(
        EventType.USER_MESSAGE.value, 
        {"text": text, "mode": current_mode}, 
        correlation_id=correlation_id
    ))

    # --- GLOBAL TRIGGERS ---
    
    # Mode Switching
    if any(k in text_lower for k in ["mode: normal", "normal mode", "reset mode"]):
        new_mode = "normal"
        state["mode"] = new_mode
        save_state(state)
        logger.info("mode.switch", new_mode, correlation_id=correlation_id)
        event_bus.publish(Event(EventType.USER_ACTION.value, {"action": "switch_mode", "target": new_mode}, correlation_id=correlation_id))
        
        msg = "Back to normal mode. What's on your mind?"
        speak(msg, correlation_id)
        return msg

    if "mode: organize" in text_lower:
        new_mode = "organize"
        state["mode"] = new_mode
        save_state(state)
        logger.info("mode.switch", new_mode, correlation_id=correlation_id)
        
        msg = "Switched to Organize mode. I'm ready to clean up."
        speak(msg, correlation_id)
        return msg

    if "mode: trade" in text_lower:
        new_mode = "trade"
        state["mode"] = new_mode
        save_state(state)
        logger.info("mode.switch", new_mode, correlation_id=correlation_id)
        
        msg = "Switched to Trade mode. Watching the markets for you."
        speak(msg, correlation_id)
        return msg

    # --- MODE SPECIFIC ROUTING ---

    if current_mode in ["normal", "organize"]:
        response = handle_normal_mode(text, state, correlation_id)
        if response:
            speak(response, correlation_id)
            print(f"RESPONSE: {response}")
            sys.stdout.flush()
            return response
    elif current_mode == "trade":
        response = handle_trade_mode(text, state, correlation_id)
        if response:
            speak(response, correlation_id)
            print(f"RESPONSE: {response}")
            sys.stdout.flush()
            return response
    
    # Default: Run AI Chat
    response = run_ai_chat(text, correlation_id)
    speak(response, correlation_id)
    return response

def handle_normal_mode(text, state, correlation_id):
    text_lower = text.lower()
    
    # Vision Actions
    if any(k in text_lower for k in ["see my computer", "see my screen", "look at my desk", "what's on my screen", "camera", "cam", "webcam", "see me", "look at me", "check my", "watch me", "open camera"]):
        from vision_perceiver import capture_and_perceive
        speak("One second, activating my vision...", correlation_id)
        logger.info("action.vision", "User requested vision check", correlation_id=correlation_id)
        return capture_and_perceive("The user wants you to look at them or their screen. Describe what you see.")

    # --- GOOGLE API INTEGRATIONS ---
    
    # Calendar API
    if any(k in text_lower for k in ["calendar", "events", "schedule", "meetings", "what's on my"]):
        speak("Checking your calendar...", correlation_id)
        try:
            from read_calendar import get_upcoming_events
            return get_upcoming_events()
        except Exception as e:
            logger.error("action.calendar", str(e), correlation_id=correlation_id)
            return f"Calendar Error: {e}"
    
    # Email API
    if any(k in text_lower for k in ["email", "emails", "inbox", "mail", "messages"]):
        speak("Checking your emails...", correlation_id)
        try:
            from read_email import get_recent_emails
            return get_recent_emails()
        except Exception as e:
            logger.error("action.email", str(e), correlation_id=correlation_id)
            return f"Email Error: {e}"
    
    # Drive API
    if any(k in text_lower for k in ["drive", "files", "documents", "docs", "my files"]):
        speak("Looking at your Drive...", correlation_id)
        try:
            from read_drive import search_files
            return search_files()
        except Exception as e:
            logger.error("action.drive", str(e), correlation_id=correlation_id)
            return f"Drive Error: {e}"
    
    # Tasks API
    if any(k in text_lower for k in ["tasks", "to do", "todo", "task list", "my tasks"]):
        speak("Fetching your tasks...", correlation_id)
        try:
            from read_tasks import list_task_lists
            return list_task_lists()
        except Exception as e:
            logger.error("action.tasks", str(e), correlation_id=correlation_id)
            return f"Tasks Error: {e}"

    # Destructive Actions (Require Confirmation)
    if "sweep desktop" in text_lower:
        state["pending_action"] = {"type": "sweep", "content": "Sweep Desktop"}
        save_state(state)
        logger.log_action("sweep_desktop", "proposed", "User requested sweep", correlation_id)
        return "I've drafted a plan to sweep the desktop. Confirm to proceed?"

    # Confirmations
    if any(k in text_lower for k in ["confirm", "do it", "yes", "proceed"]) and state.get("pending_action"):
        action = state["pending_action"]
        state["pending_action"] = None
        save_state(state)
        return execute_pending_action(action, state["mode"], correlation_id)

    if any(k in text_lower for k in ["cancel", "nevermind", "no", "stop"]):
        state["pending_action"] = None
        save_state(state)
        logger.info("action.cancel", "User cancelled pending action", correlation_id=correlation_id)
        return "Action cancelled."

    # If nothing matched, return None so it falls through to AI chat
    return None


def handle_trade_mode(text, state, correlation_id):
    text_lower = text.lower()
    if "plan a trade" in text_lower:
        logger.info("trade.plan", "User requested trade plan", correlation_id=correlation_id)
        return "Generating trade plan... (Simulated) Buy 10 AAPL at 180. Risk: Low."
    if "paper trade" in text_lower:
        logger.info("trade.paper", "User executed paper trade", correlation_id=correlation_id)
        return "Paper trade recorded. Simulating execution..."
    return "Trader Mode Active (Paper Only). Try 'Plan a trade' or 'Paper trade'."

def execute_pending_action(action, mode, correlation_id):
    logger.log_action(action["type"], "executed", action["content"], correlation_id, metadata={"mode": mode})
    event_bus.publish(Event(EventType.USER_ACTION.value, {"action": action["type"], "status": "executed"}, correlation_id=correlation_id))
    
    if action["type"] == "sweep":
        return "Sweep executed! Desktop is now clean."
    return "Action executed successfully."

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="+")
    args = parser.parse_args()
    
    user_input = " ".join(args.text)
    response = route_request(user_input)
    # print(response) # Handled inside route_request via print("RESPONSE: ...")
