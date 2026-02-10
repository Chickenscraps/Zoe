
import os
import sys
import json
import asyncio
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Setup paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from database import init_db, MessageRepository, MessageEvent, get_db
from cadence_engine import CadenceEngine
from voice_worker import VoiceWorker, TranscriptEvent

def test_cadence_logic():
    print("\n🧪 Testing Cadence Engine...")
    engine = CadenceEngine()
    
    # Initial state: 0 heat
    assert engine.heat_score == 0.0
    print("   Initial heat: 0.0 (Correct)")
    
    # Add some messages
    print("   Simulating 5 messages...")
    for _ in range(5):
        engine.update_activity()
    
    # Expected: 5/20 = 0.25
    print(f"   Heat after 5: {engine.heat_score}")
    assert 0.2 < engine.heat_score < 0.3
    
    # Test Quiet Hours
    # Mock time to be 4 AM
    original_quiet_check = engine.is_quiet_hours
    engine.is_quiet_hours = lambda: True
    
    should = engine.should_respond(is_mentioned=False, is_reply=False)
    assert should is False
    print("   Quiet hours respected (No proactive response)")
    
    # Test Mention Override
    should = engine.should_respond(is_mentioned=True, is_reply=False)
    assert should is True
    print("   Mention overrides quiet hours (Correct)")

def test_message_persistence():
    print("\n🧪 Testing Message Repository...")
    init_db()
    
    msg_id = "test_msg_1"
    msg = MessageEvent(
        id=msg_id,
        source="discord",
        channel_id="123",
        user_id="456",
        content="Hello world",
        timestamp=datetime.now().isoformat(),
        profile_id="test_user"
    )
    
    MessageRepository.insert(msg)
    
    # Retrieve
    recent = MessageRepository.get_recent(channel_id="123", limit=1)
    assert len(recent) == 1
    assert recent[0].content == "Hello world"
    print("   Message inserted and retrieved.")
    
    # Stats
    stats = MessageRepository.get_stats_now()
    print(f"   Total messages in DB: {stats['count']}")
    assert stats['count'] > 0

def test_voice_persistence_mock():
    print("\n🧪 Testing Voice Transcript Persistence (Mock)...")
    
    # Mock bot
    mock_bot = MagicMock()
    worker = VoiceWorker(mock_bot)
    worker.session.logging_enabled = True # Important!
    
    # Mock database insert because we don't want to depend on actual DB in this unit test if possible,
    # but since we are integration testing, let's use the real DB from test_message_persistence.
    # The worker imports database internally, so it will use our initialized DB.
    
    event = TranscriptEvent(
        speaker_id="789",
        text="Voice test message",
        confidence=0.95,
        timestamp=datetime.now(),
        profile_id="voice_user"
    )
    
    # We can't await in sync main, so run async
    async def run_voice_persist():
        await worker._persist_transcript(event)
    
    asyncio.run(run_voice_persist())
    
    # Verify in DB
    with get_db() as conn:
        row = conn.execute("SELECT * FROM message_events WHERE user_id = '789'").fetchone()
        assert row is not None
        assert row["content"] == "Voice test message"
        assert row["source"] == "voice"
    
    print("   Voice transcript saved as message.")

if __name__ == "__main__":
    test_cadence_logic()
    test_message_persistence()
    test_voice_persistence_mock()
