"""
Verification script for AGI Architecture Upgrade
Tests: Safety, VAD, Scheduler, Novelty Engine
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

def test_risk_registry():
    print("\n🧪 Testing RISK_REGISTRY...")
    from approval_gate import RISK_REGISTRY, RiskLevel, ApprovalGate
    
    # Check registry has entries
    assert len(RISK_REGISTRY) > 10, "Should have many tools registered"
    
    # Check risk levels
    assert RISK_REGISTRY["time_get"] == RiskLevel.LOW
    assert RISK_REGISTRY["delete_file"] == RiskLevel.CRITICAL
    assert RISK_REGISTRY["write_file"] == RiskLevel.HIGH
    
    print(f"   ✅ {len(RISK_REGISTRY)} tools in registry")
    print("✅ RISK_REGISTRY works!")

def test_enforce_logic():
    print("\n🧪 Testing enforce() logic...")
    from approval_gate import ApprovalGate, ROOT_ADMIN_ID
    
    # Mock bot
    class MockBot:
        pass
    
    gate = ApprovalGate(MockBot())
    
    # LOW risk should allow
    result = gate.enforce("time_get", {}, 123456)
    assert result == "ALLOW", f"LOW risk should ALLOW, got {result}"
    
    # CRITICAL from non-admin should deny
    result = gate.enforce("delete_file", {"path": "/tmp/x"}, 123456)
    assert result == "DENY", f"CRITICAL from non-admin should DENY, got {result}"
    
    # CRITICAL from admin should allow
    result = gate.enforce("delete_file", {"path": "/tmp/x"}, ROOT_ADMIN_ID)
    assert result == "ALLOW", f"CRITICAL from admin should ALLOW, got {result}"
    
    # HIGH from non-admin should require approval
    result = gate.enforce("write_file", {"path": "/tmp/x"}, 123456)
    assert result == "REQUIRE_APPROVAL", f"HIGH from non-admin should REQUIRE_APPROVAL, got {result}"
    
    print("✅ enforce() logic correct!")

def test_audit_log():
    print("\n🧪 Testing audit logging...")
    from approval_gate import log_audit, RiskLevel, AUDIT_LOG_PATH
    import os
    
    # Log a test entry
    log_audit(12345, "test_tool", {"arg": "value"}, RiskLevel.LOW, "TEST")
    
    # Check file exists
    assert os.path.exists(AUDIT_LOG_PATH), "Audit log should exist"
    
    # Check entry was written
    with open(AUDIT_LOG_PATH, "r") as f:
        content = f.read()
    assert "test_tool" in content, "Test entry should be in audit log"
    
    print(f"   Log at: {AUDIT_LOG_PATH}")
    print("✅ Audit logging works!")

def test_vad_filter():
    print("\n🧪 Testing VAD Filter...")
    from vad_filter import VADFilter, is_speech_simple
    
    vad = VADFilter(aggressiveness=2)
    
    # Test with silence (zeros)
    silence = bytes(2880)  # 30ms of silence
    assert not vad.is_speech(silence), "Silence should not be speech"
    
    # Test state
    assert not vad.is_active(), "Should not be active initially"
    
    print("✅ VAD Filter initialized!")

def test_scheduler_jobs():
    print("\n🧪 Testing scheduler jobs import...")
    from scheduler_jobs import morning_brief, night_shift, novelty_check
    
    # Just verify they're callable
    assert callable(morning_brief)
    assert callable(night_shift)
    assert callable(novelty_check)
    
    print("✅ Scheduler jobs importable!")

def test_novelty_engine():
    print("\n🧪 Testing Novelty Engine...")
    from news_fetcher import calculate_relevance, get_wild_item
    
    # Test relevance scoring
    score1 = calculate_relevance("GTA6 Trailer Released Today")
    score2 = calculate_relevance("Random boring headline")
    
    assert score1 > score2, f"Gaming headline should score higher ({score1} vs {score2})"
    
    score3 = calculate_relevance("OpenAI announces GPT-5")
    assert score3 > 0, f"AI headline should have positive score ({score3})"
    
    print(f"   GTA6 headline: {score1}")
    print(f"   OpenAI headline: {score3}")
    print("✅ Novelty Engine works!")

def test_start_script():
    print("\n🧪 Testing start_zoe.bat exists...")
    import os
    
    bat_path = os.path.join(PROJECT_ROOT, "start_zoe.bat")
    assert os.path.exists(bat_path), "start_zoe.bat should exist"
    
    with open(bat_path, "r") as f:
        content = f.read()
    assert "42" in content, "Should check for exit code 42 (hot reload)"
    
    print("✅ start_zoe.bat configured correctly!")

if __name__ == "__main__":
    test_risk_registry()
    test_enforce_logic()
    test_audit_log()
    test_vad_filter()
    test_scheduler_jobs()
    test_novelty_engine()
    test_start_script()
    
    print("\n🎉 All AGI Architecture Upgrade tests passed!")
