import pytest
import json
from safety_layer.sanitize import sanitize_inbound_text, sanitize_outbound_text
from context.room_context import RoomContextBuilder, prepare_message_for_context

def test_sanitize_inbound():
    text = "Hey <@123456>, check this out: https://google.com\nNew lines are bad."
    sanitized = sanitize_inbound_text(text)
    assert "@user" in sanitized
    assert "[link]" in sanitized
    assert "\n" not in sanitized
    assert len(sanitized) <= 240

def test_sanitize_outbound():
    text = """
    Thought for the user: I should do this.
    Reasoned: Market is up.
    ```python
    print("leak")
    ```
    {"path": "C:\\secrets.txt"}
    Real answer: everything is fine.
    """
    sanitized = sanitize_outbound_text(text)
    assert "Thought for" not in sanitized
    assert "Reasoned" not in sanitized
    assert "```" not in sanitized
    assert '"path"' not in sanitized
    assert "everything is fine" in sanitized
    assert len(sanitized) <= 1800

def test_room_context_builder():
    messages = [
        prepare_message_for_context("Josh", "admin", "pnl is looking good lol"),
        prepare_message_for_context("Steve", "user", "yeah, nice win on spy"),
    ]
    ctx_json = RoomContextBuilder.build(123, 456, messages)
    ctx = json.loads(ctx_json)
    
    assert ctx['channel_id'] == "123"
    assert ctx['active_topic'] == "trading"
    assert ctx['tone'] == "hyped" or ctx['tone'] == "chill" # 'lol' -> chill, 'win' -> hyped. Topic priority or tone priority?
    assert "participants" in ctx
    assert len(ctx['last_messages']) == 2
    assert "Vibe:" in ctx['room_summary']

def test_outbound_fallback():
    text = "Thought for me: only reasoning here."
    sanitized = sanitize_outbound_text(text)
    assert sanitized == "Got it. Give me one sec—what’s the goal here?"

if __name__ == "__main__":
    # Manual run if pytest not installed or for quick check
    test_sanitize_inbound()
    test_sanitize_outbound()
    test_room_context_builder()
    test_outbound_fallback()
    print("✅ All local tests passed!")
