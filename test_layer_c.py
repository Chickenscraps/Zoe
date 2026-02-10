"""
Test Layer C Tools (Vision Desktop)
"""
import time
import layer_c_tools
import pyautogui

def test_layer_c():
    print("\n--- Testing Layer C Tools ---")

    # 1. Screen Info
    print("Getting Screen Info...")
    info = layer_c_tools.get_screen_info()
    print(info)
    
    # 2. Capture Screen
    print("Capturing Screen...")
    res = layer_c_tools.capture_screen()
    print(res)
    
    # 3. Mouse Safety Test
    # Move mouse slightly to sanity check control
    print("Moving mouse to (100, 100)...")
    try:
        pyautogui.moveTo(100, 100)
        print("✅ Mouse moved.")
        time.sleep(1)
    except Exception as e:
        print(f"❌ Mouse move failed: {e}")
        
    print("\nTest Complete.")

if __name__ == "__main__":
    test_layer_c()
