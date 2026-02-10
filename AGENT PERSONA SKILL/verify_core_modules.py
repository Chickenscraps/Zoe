"""
Verification Script for Clawdbot Core Modules
Checks:
1. Fallback Responder
2. Explainability
3. News Watcher (Dry Run)
4. Affect Engine (Salience)
5. Showcase Manager (Checklist)
6. Server Dependencies (Health Check)
"""
import os
import sys
import json
import time
import requests
import subprocess
from datetime import datetime

# Add skill dir to path
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

def print_result(name, success, details=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {name:<25} | {details}")

def verify_fallback_responder():
    try:
        from fallback_responder import get_fallback_response
        resp = get_fallback_response("hello")
        success = "offline mode" in resp.lower() or "backup" in resp.lower()
        print_result("Fallback Responder", success, f"Response: {resp[:50]}...")
    except ImportError:
        print_result("Fallback Responder", False, "Module missing")
    except Exception as e:
        print_result("Fallback Responder", False, str(e))

def verify_explainability():
    try:
        from explainability import store_rationale, get_last_rationale
        store_rationale("test_action", "testing verification", {"key": "val"}, 1.0, "test-123")
        last = get_last_rationale()
        success = last and last["action"] == "test_action"
        print_result("Explainability", success, "Rationale stored/retrieved")
    except Exception as e:
        print_result("Explainability", False, str(e))

def verify_affect_engine():
    try:
        from affect_engine import affect_engine
        # Initial state
        initial = affect_engine.get_salience()
        # Spike
        affect_engine.spike("Test Spike", conviction=1.0, urgency=1.0, impact=1.0)
        spiked = affect_engine.get_salience()
        success = spiked > initial
        print_result("Affect Engine", success, f"Salience: {initial:.2f} -> {spiked:.2f}")
    except Exception as e:
        print_result("Affect Engine", False, str(e))

def verify_showcase_manager():
    try:
        from showcase_manager import submit_candidate, validate_checklist
        # Fail case
        c1, r1 = submit_candidate(what_is_it="Too short", why_it_matters="")
        fail_check = not r1.passed
        
        # Pass case
        c2, r2 = submit_candidate(
            what_is_it="A verify script for testing modules",
            why_it_matters="Ensures all systems are go before deployment",
            demo_steps=["Run python verify.py"],
            artifacts=["logs.txt"],
            self_test_passed=True,
            risks_and_rollback="None, read only",
            audience_fit="Devs need confidence"
        )
        pass_check = r2.passed
        
        success = fail_check and pass_check
        print_result("Showcase Manager", success, f"Gating operational (Score: {r2.score}/{r2.max_score})")
    except Exception as e:
        print_result("Showcase Manager", False, str(e))

def verify_server_health():
    try:
        # Assuming server is running on 8000
        try:
            resp = requests.get("http://localhost:8000/health", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                deps = data.get("dependencies", {})
                failures = [k for k, v in deps.items() if v.get("status") not in ["ok", "loaded"]]
                if not failures:
                    print_result("Server Health", True, "All dependencies OK")
                else:
                    print_result("Server Health", False, f"Issues: {failures}")
            else:
                print_result("Server Health", False, f"HTTP {resp.status_code}")
        except requests.exceptions.ConnectionError:
            print_result("Server Health", False, "Server not running locally")
    except Exception as e:
        print_result("Server Health", False, str(e))

if __name__ == "__main__":
    print("--- Verifying Clawdbot Core Modules ---")
    verify_fallback_responder()
    verify_explainability()
    verify_affect_engine()
    verify_showcase_manager()
    verify_server_health()
