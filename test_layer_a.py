"""
Test Layer A Tools (Browser)
"""
import time
import layer_a_tools

def test_browser_tools():
    print("\n--- Testing Browser Tools ---")
    
    # 1. Launch
    print("Launching browser (Headless)...")
    res = layer_a_tools.launch_browser(headless=True, url="https://example.com")
    print(res)
    time.sleep(2)
    
    # 2. Snapshot
    print("Taking snapshot...")
    snapshot = layer_a_tools.browser_snapshot()
    print("--- Snapshot Content ---")
    print(snapshot[:500]) # Print first 500 chars
    print("------------------------")
    
    if "Example Domain" in snapshot:
        print("✅ Correctly loaded Example Domain")
    else:
        print("❌ Failed to verify page content")
        
    # 3. Navigation
    print("\nNavigating to google.com...")
    res = layer_a_tools.browser_navigate("https://www.google.com")
    print(res)
    time.sleep(1)
    
    # 4. Snapshot again
    snapshot = layer_a_tools.browser_snapshot()
    if "Google" in snapshot:
        print("✅ Correctly loaded Google")
    else:
        print(f"❌ Failed to verify Google ({snapshot[:100]}...)")
        
    print("\nTest Complete.")

if __name__ == "__main__":
    test_browser_tools()
