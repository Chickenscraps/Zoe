
import sys
import os
import json
import time

# Add Skill dir to path
SKILL_DIR = os.path.join(os.getcwd(), "AGENT PERSONA SKILL")
sys.path.append(SKILL_DIR)

print("🧪 Starting System Verification Suite...\n")

# 1. Test Memory Engine
try:
    from memory_store import init_db, set_preference, get_memory_context
    init_db()
    set_preference("user_test", "verified")
    context = get_memory_context()
    if 'user_test' in context:
        print("✅ Memory Engine: SQLite initialization and context retrieval successful.")
    else:
        print("❌ Memory Engine: Context retrieval failed.")
except Exception as e:
    print(f"❌ Memory Engine Error: {e}")

# 2. Test Notification Router
try:
    from notification_router import route_attention
    # Test quiet hours suppression logic? We'll just test a normal send
    success = route_attention("Verification", "Residency AI features are being verified.", urgency="critical", speaks=False)
    if success:
        print("✅ Notification Router: Broadcast successful.")
    else:
        print("❌ Notification Router: Broadcast suppressed or failed.")
except Exception as e:
    print(f"❌ Notification Router Error: {e}")

# 3. Test Resilience Layer (Circuit Breaker)
try:
    from resilience import gemini_breaker, resilient_call
    def fail_func():
        raise Exception("Simulated Gemini Failure")
    
    print("Testing Circuit Breaker (expecting 5 failures to trip)...")
    for _ in range(5):
        try:
            resilient_call(fail_func)
        except:
            pass
            
    if gemini_breaker.state == "OPEN":
        print("✅ Resilience: Circuit Breaker TRIPPED successfully after failures.")
        # Test degraded response
        resp = resilient_call(fail_func)
        if "offline mode" in resp:
            print("✅ Resilience: Degraded mode response successful.")
    else:
        print(f"❌ Resilience: Circuit Breaker state is {gemini_breaker.state} (Expected OPEN).")
except Exception as e:
    print(f"❌ Resilience Error: {e}")

# 4. Test Rationale/Explainability
try:
    from journal import log_event
    log_event("test.verify", "Checking explainability", mode="normal", rationale="System verification check")
    print("✅ Explainability: Event logged with rationale.")
except Exception as e:
    print(f"❌ Explainability Error: {e}")

print("\n🏁 Verification Complete.")
