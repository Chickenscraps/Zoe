"""
Integration Self-Test for AI Coder / Antigravity API Proxy

Run this to verify which backend is working:
  python test_ai_coder.py
"""
import os
import sys

# Add project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(".env.secrets")


def test_antigravity_connection():
    """Test if Antigravity API Proxy is reachable."""
    import requests
    
    # Use model router which now connects to Gemini directly
    from model_router import router
    api_key = os.getenv("ANTIGRAVITY_API_KEY", "")
    
    print(f"📡 Testing Antigravity API Proxy...")
    print(f"   Base URL: {base_url}")
    print(f"   API Key: {'sk-***' + api_key[-4:] if len(api_key) > 4 else '(not set)'}")
    
    if not api_key:
        print("❌ ANTIGRAVITY_API_KEY not set in .env.secrets")
        return False
    
    # Try health check or models endpoint
    try:
        # Try /models first (common OpenAI-compatible endpoint)
        r = requests.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
        if r.status_code == 200:
            print(f"✅ Antigravity proxy is reachable!")
            models = r.json().get("data", [])
            if models:
                print(f"   Available models: {[m.get('id', m) for m in models[:5]]}")
            return True
        else:
            print(f"⚠️ Antigravity responded with status {r.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Antigravity at {base_url}")
        print("   Is the Antigravity API Proxy running?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_ask_coder():
    """Test ask_coder with a trivial prompt."""
    from ai_coder import ask_coder
    
    print("\n🧪 Testing ask_coder() with trivial prompt...")
    
    result = ask_coder(
        task="Return ONLY the text 'Hello from AI' - nothing else.",
        context="This is a connectivity test."
    )
    
    if "Error" in result and "All AI backends failed" in result:
        print(f"❌ ask_coder failed:\n{result}")
        return False
    else:
        print(f"✅ ask_coder succeeded!")
        print(f"   Response preview: {result[:100]}...")
        return True


def test_policy():
    """Test folder policy enforcement."""
    from ai_coder import check_path_policy, check_extension_policy
    
    print("\n🔒 Testing folder policy enforcement...")
    
    # Should be allowed
    allowed_path = r"C:\Users\josha\OneDrive\Desktop\Zoes\test-project\index.html"
    allowed, reason = check_path_policy(allowed_path)
    print(f"   {allowed_path}")
    print(f"   → Allowed: {allowed} ({reason})")
    
    # Should be denied
    denied_path = r"C:\Windows\System32\evil.exe"
    denied, reason = check_path_policy(denied_path)
    print(f"   {denied_path}")
    print(f"   → Allowed: {denied} ({reason})")
    
    # Extension check
    ext_allowed, ext_reason = check_extension_policy("test.html")
    print(f"   test.html → Allowed: {ext_allowed}")
    
    ext_denied, ext_reason = check_extension_policy("virus.exe")
    print(f"   virus.exe → Allowed: {ext_denied}")
    
    return True


def main():
    print("=" * 60)
    print("AI CODER INTEGRATION SELF-TEST")
    print("=" * 60)
    
    results = {
        "Antigravity Connection": test_antigravity_connection(),
        "ask_coder Function": test_ask_coder(),
        "Folder Policy": test_policy()
    }
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test}: {status}")
    
    all_passed = all(results.values())
    print("\n" + ("🎉 All tests passed!" if all_passed else "⚠️ Some tests failed."))
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
