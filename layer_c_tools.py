"""
Layer C Tools: Vision Desktop (Experimental)
Uses PyAutoGUI to give Zoe "eyes and hands" for pixel-based automation.
"""
import os
import time
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import
try:
    import pyautogui
    # FAILSAFE: Moving mouse to upper-left corner aborts everything
    pyautogui.FAILSAFE = True
    # PAUSE: Default 1.0s pause between actions for safety
    pyautogui.PAUSE = 1.0
    _HAS_GUI = True
except ImportError:
    _HAS_GUI = False
    logger.error("PyAutoGUI not installed. Layer C disabled.")


def capture_screen(region: Optional[Tuple[int, int, int, int]] = None) -> str:
    """
    Capture the screen and return a file path.
    region: (left, top, width, height) tuple, or None for full screen.
    """
    if not _HAS_GUI: return "❌ System lacks GUI tools."
    
    try:
        timestamp = int(time.time())
        filename = f"screen_{timestamp}.png"
        path = os.path.join(os.getcwd(), "temp_vision", filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        screenshot = pyautogui.screenshot(region=region)
        screenshot.save(path)
        
        return f"📸 Screenshot captured: {path}"
        
    except Exception as e:
        return f"❌ Capture failed: {e}"


def get_screen_info() -> str:
    """Return resolution and mouse position."""
    if not _HAS_GUI: return "❌ System lacks GUI tools."
    
    try:
        width, height = pyautogui.size()
        x, y = pyautogui.position()
        return f"🖥️ Screen Size: {width}x{height} | 🖱️ Mouse at ({x}, {y})"
    except Exception as e:
        return f"❌ Failed to get info: {e}"


def mouse_click(x: int, y: int, clicks: int = 1, button: str = 'left') -> str:
    """
    Move mouse to x,y and click.
    Safety: Verifies coordinates are within screen bounds.
    """
    if not _HAS_GUI: return "❌ System lacks GUI tools."
    
    try:
        # Bounds check
        w, h = pyautogui.size()
        if not (0 <= x < w and 0 <= y < h):
            return f"❌ Coordinates ({x}, {y}) out of bounds ({w}x{h})."
            
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)
        return f"✅ Clicked at ({x}, {y})"
        
    except pyautogui.FailSafeException:
        return "❌ Failsafe triggered (Mouse in corner). Action aborted."
    except Exception as e:
        return f"❌ Click failed: {e}"


def keyboard_type(text: str, interval: float = 0.05) -> str:
    """Type text safely."""
    if not _HAS_GUI: return "❌ System lacks GUI tools."
    
    try:
        # Limit length prevents massive accidental pastes
        if len(text) > 500:
            return "❌ Text too long (>500 chars). Use clipboard instead (not impl)."
            
        pyautogui.write(text, interval=interval)
        return f"✅ Typed {len(text)} characters."
        
    except Exception as e:
        return f"❌ Typing failed: {e}"


def keyboard_hotkey(keys: str) -> str:
    """
    Press hotkeys. Format: 'ctrl,c', 'alt,tab', 'enter'.
    Multiple keys separated by comma.
    """
    if not _HAS_GUI: return "❌ System lacks GUI tools."
    
    try:
        key_list = [k.strip().lower() for k in keys.split(',')]
        pyautogui.hotkey(*key_list)
        return f"✅ Pressed: {' + '.join(key_list)}"
        
    except Exception as e:
        return f"❌ Hotkey failed: {e}"
