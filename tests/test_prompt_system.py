"""
Tests for the prompt composition and sanitization system.

Run: python -m pytest tests/test_prompt_system.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from prompt_loader import build_system_prompt, _load_prompt_file
from safety_layer.sanitize import sanitize_outbound_text, sanitize_inbound_text, enforce_allowlist_mentions
from cadence_engine import CadenceEngine


# ─── Prompt Loader Tests ───

class TestPromptLoader:
    """Tests for file-based prompt composition."""

    MOCK_CONFIG = {
        "admin": {"admin_user_ids": ["292890243852664855"]},
        "persona": {
            "mention_allowlist": ["Josh", "Steve"],
            "boundary_words": ["stop", "no"],
            "flirt_mode": False,
        },
        "idle": {"cooldown_minutes": 30, "min_silence_minutes": 10},
    }

    def test_loads_all_prompt_files(self):
        """All four prompt files should load without error."""
        for f in ["system.md", "persona.md", "trading_policy.md", "room_context.md"]:
            content = _load_prompt_file(f)
            assert content, f"Prompt file {f} was empty or missing"
            assert len(content) > 100, f"Prompt file {f} too short ({len(content)} chars)"

    def test_compose_includes_all_sections(self):
        """Composed prompt should include content from all prompt files."""
        prompt = build_system_prompt(config=self.MOCK_CONFIG)
        assert "MODEL IDENTITY" in prompt, "Missing system.md content"
        assert "VOICE" in prompt, "Missing persona.md content"
        assert "PAPER-ONLY" in prompt, "Missing trading_policy.md content"
        assert "CURRENT SESSION" in prompt, "Missing dynamic context"
        assert "IDENTITY GUARD" in prompt, "Missing identity guard"

    def test_compose_with_room_context(self):
        """ROOM_CONTEXT should be included when provided."""
        ctx = '{"channel_id": "123", "active_topic": "trading"}'
        prompt = build_system_prompt(config=self.MOCK_CONFIG, room_context_json=ctx)
        assert "ROOM_CONTEXT" in prompt
        assert "trading" in prompt

    def test_compose_with_startup(self):
        """Startup ritual tag should appear when is_startup=True."""
        prompt = build_system_prompt(config=self.MOCK_CONFIG, is_startup=True)
        assert "[STARTUP RITUAL]" in prompt

    def test_compose_without_startup(self):
        """No startup tag when is_startup=False."""
        prompt = build_system_prompt(config=self.MOCK_CONFIG, is_startup=False)
        assert "[STARTUP RITUAL]" not in prompt

    def test_compose_with_goals(self):
        """Goals should be included when provided."""
        prompt = build_system_prompt(config=self.MOCK_CONFIG, goals="Scan SPY for reversals")
        assert "Scan SPY for reversals" in prompt

    def test_compose_with_memories(self):
        """Memories should be included when provided."""
        prompt = build_system_prompt(
            config=self.MOCK_CONFIG, memories=["Josh prefers credit spreads"]
        )
        assert "Josh prefers credit spreads" in prompt

    def test_prompt_caching(self):
        """Second load should use cache (same mtime)."""
        content1 = _load_prompt_file("system.md")
        content2 = _load_prompt_file("system.md")
        assert content1 == content2


# ─── Outbound Sanitization Tests ───

class TestOutboundSanitization:
    """Tests that internal traces never reach Discord."""

    def test_strips_thought_tags(self):
        text = "hello <thought>internal reasoning here</thought> world"
        result = sanitize_outbound_text(text)
        assert "<thought>" not in result
        assert "internal reasoning" not in result
        assert "hello" in result

    def test_strips_thought_for_pattern(self):
        text = "Thought for 5 seconds about this.\nHere's my answer."
        result = sanitize_outbound_text(text)
        assert "Thought for" not in result

    def test_strips_permission_check(self):
        text = "Permission check: user=123, tools=true\nSure, I can help."
        result = sanitize_outbound_text(text)
        assert "Permission check" not in result

    def test_strips_user_wants_pattern(self):
        text = "The user wants me to check the market.\nLooking at SPY now."
        result = sanitize_outbound_text(text)
        assert "The user wants" not in result

    def test_strips_modules_loaded(self):
        text = "Modules loaded successfully.\nI'm ready."
        result = sanitize_outbound_text(text)
        assert "Modules loaded" not in result
        assert "ready" in result

    def test_strips_stack_trace(self):
        text = "here is info\nstack trace at line 42\nmore info"
        result = sanitize_outbound_text(text)
        assert "stack trace" not in result

    def test_strips_json_tool_calls(self):
        text = 'Sure! {"name": "list_dir", "parameters": {"path": "C:\\\\Users"}}'
        result = sanitize_outbound_text(text)
        assert '"name":' not in result

    def test_strips_function_call(self):
        text = "function_call: get_price(SPY)\nSPY is at $450"
        result = sanitize_outbound_text(text)
        assert "function_call" not in result

    def test_strips_reasoning_line(self):
        text = "Reasoning: the user asked about SPY\nSPY looks bullish."
        result = sanitize_outbound_text(text)
        assert "Reasoning:" not in result
        assert "SPY looks bullish" in result

    def test_preserves_normal_text(self):
        text = "spy is looking interesting today. might open a spread."
        result = sanitize_outbound_text(text)
        assert result == text

    def test_empty_input_returns_empty(self):
        assert sanitize_outbound_text("") == ""
        assert sanitize_outbound_text(None) == ""

    def test_all_stripped_returns_fallback(self):
        text = "Thought for 3 seconds"
        result = sanitize_outbound_text(text)
        assert result == "Got it. Give me one sec\u2014what\u2019s the goal here?"

    def test_caps_at_1800(self):
        text = "a" * 2000
        result = sanitize_outbound_text(text)
        assert len(result) <= 1800

    def test_collapses_blank_lines(self):
        text = "line 1\n\n\n\n\nline 2"
        result = sanitize_outbound_text(text)
        assert "\n\n\n" not in result


# ─── Inbound Sanitization Tests ───

class TestInboundSanitization:

    def test_strips_mentions(self):
        text = "hey <@292890243852664855> what's up"
        result = sanitize_inbound_text(text)
        assert "@user" in result
        assert "292890243852664855" not in result

    def test_strips_links(self):
        text = "check this https://example.com/page"
        result = sanitize_inbound_text(text)
        assert "[link]" in result
        assert "https" not in result

    def test_caps_at_240(self):
        text = "a" * 500
        result = sanitize_inbound_text(text)
        assert len(result) == 240


# ─── Allowlist Tests ───

class TestAllowlistEnforcement:

    def test_scrubs_admin_keyword(self):
        text = "the admin said we should do this"
        result = enforce_allowlist_mentions(text, ["Josh"])
        assert "admin" not in result.lower()
        assert "ops" in result

    def test_scrubs_raw_discord_ids(self):
        text = "user 292890243852664855 said hi"
        result = enforce_allowlist_mentions(text, ["Josh"])
        assert "292890243852664855" not in result
        assert "[redacted-id]" in result

    def test_preserves_normal_text(self):
        text = "Josh said the market looks good"
        result = enforce_allowlist_mentions(text, ["Josh"])
        assert result == text


# ─── Cadence Engine Tests ───

class TestCadenceEngine:

    def test_init_with_config(self):
        engine = CadenceEngine(idle_config={
            "cooldown_minutes": 45,
            "min_silence_minutes": 15,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        })
        assert engine._cooldown_seconds == 45 * 60
        assert engine._min_silence_seconds == 15 * 60

    def test_init_with_defaults(self):
        engine = CadenceEngine()
        assert engine._cooldown_seconds == 30 * 60
        assert engine._min_silence_seconds == 10 * 60

    def test_heat_starts_at_zero(self):
        engine = CadenceEngine()
        assert engine.heat_score == 0.0


# ─── Integration: Gemini-Only Enforcement ───

class TestGeminiOnlyPolicy:
    """Tests that non-Gemini models are rejected at the router level."""

    def test_model_router_rejects_llama(self):
        from model_router import ModelRouter
        router = ModelRouter.__new__(ModelRouter)
        # Manually set the attributes without calling __init__ (avoids API call)
        router.flash_lite_model = "gemini-2.5-flash-lite"
        router.ALLOWED_MODEL_PREFIXES = ("gemini-",)
        assert router._validate_model("llama-3.1-70b") == "gemini-2.5-flash-lite"

    def test_model_router_accepts_gemini(self):
        from model_router import ModelRouter
        router = ModelRouter.__new__(ModelRouter)
        router.flash_lite_model = "gemini-2.5-flash-lite"
        router.ALLOWED_MODEL_PREFIXES = ("gemini-",)
        assert router._validate_model("gemini-2.5-pro") == "gemini-2.5-pro"

    def test_model_router_accepts_flash_lite(self):
        from model_router import ModelRouter
        router = ModelRouter.__new__(ModelRouter)
        router.flash_lite_model = "gemini-2.5-flash-lite"
        router.ALLOWED_MODEL_PREFIXES = ("gemini-",)
        assert router._validate_model("gemini-2.5-flash-lite") == "gemini-2.5-flash-lite"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
