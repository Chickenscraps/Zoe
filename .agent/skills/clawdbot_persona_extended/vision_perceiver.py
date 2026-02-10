
import os
import time
import json
import pyautogui
from PIL import Image
import google.generativeai as genai
from datetime import datetime

# Load Config
OPENCLAW_CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")
try:
    with open(OPENCLAW_CONFIG_PATH, "r") as f:
        config = json.load(f)
        API_KEY = config.get("env", {}).get("vars", {}).get("GEMINI_API_KEY")
except:
    API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    print("Error: GEMINI_API_KEY not found in config or environment.")
    exit(1)

genai.configure(api_key=API_KEY)

def capture_and_perceive(prompt="Describe what you see on my screen in a short, helpful way."):
    """
    Captures a screenshot and uses Gemini Vision to describe it.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"screenshot_{timestamp}.png"
    
    try:
        # Capture screen
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        
        # Initialize Gemini 2.0 Flash (vision-capable)
        model = genai.GenerativeModel('gemini-2.0-flash-001')
        
        # Upload and generate (using 'with' to ensure the file is closed)
        with Image.open(screenshot_path) as img:
            # Add persona hint
            full_prompt = f"You are Clawdbot, a proactive ops cofounder. {prompt}"
            response = model.generate_content([full_prompt, img])
            # Ensure response is generated before closing
            text_response = response.text
            
        # Cleanup
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
            
        return text_response
    except Exception as e:
        return f"Vision Error: {str(e)}"

if __name__ == "__main__":
    result = capture_and_perceive()
    print(result)
