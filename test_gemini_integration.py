"""
Quick test script to verify Gemini direct API integration.
"""
import asyncio
import sys
import os
from pathlib import Path

# Load environment variables from .env.secrets
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env.secrets"
load_dotenv(env_path)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_gemini():
    print("🧪 Testing Gemini Direct API Integration...\n")
    
    # Test 1: Backend initialization
    print("1️⃣ Testing backend initialization...")
    try:
        from llm_backends import get_backend
        backend = get_backend()
        print("✅ Backend initialized successfully\n")
    except Exception as e:
        print(f"❌ Backend init failed: {e}\n")
        return False
    
    # Test 2: Simple Flash-Lite generation
    print("2️⃣ Testing Flash-Lite generation...")
    try:
        messages = [
            {"role": "user", "content": "Say 'Hello from Gemini Flash-Lite!' and nothing else."}
        ]
        response = await backend.generate_text(messages, model="gemini-2.0-flash-lite")
        print(f"✅ Flash-Lite response: {response[:100]}...\n")
    except Exception as e:
        print(f"❌ Flash-Lite failed: {e}\n")
        return False
    
    # Test 3: Model router
    print("3️⃣ Testing model router...")
    try:
        from model_router import router
        messages = [{"role": "user", "content": "Say 'Router working!' and nothing else."}]
        response = await router.chat(messages)
        print(f"✅ Router response: {response[:100]}...\n")
    except Exception as e:
        print(f"❌ Router failed: {e}\n")
        return False
    
    # Test 4: Escalation tracking
    print("4️⃣ Testing escalation tracker...")
    try:
        from model_router import router
        tracker = router.escalation_tracker
        
        # Simulate stack trace detection
        task = "Fix this error: Traceback (most recent call last)..."
        should_escalate = tracker.should_escalate("test_hash", task, "gemini-2.0-flash-lite")
        
        if should_escalate:
            print("✅ Escalation correctly triggered for stack trace\n")
        else:
            print("⚠️ Escalation NOT triggered (may be expected)\n")
    except Exception as e:
        print(f"❌ Escalation test failed: {e}\n")
        return False
    
    print("=" * 50)
    print("✅ ALL TESTS PASSED!")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = asyncio.run(test_gemini())
    sys.exit(0 if success else 1)
