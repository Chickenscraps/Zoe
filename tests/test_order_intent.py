"""Tests for order intent state machine."""
import pytest
from services.order_lifecycle.intent import OrderIntent, VALID_TRANSITIONS, TERMINAL_STATES


class TestOrderIntentStateMachine:
    """Test all state transitions."""

    def test_initial_state(self):
        intent = OrderIntent()
        assert intent.status == "created"
        assert not intent.is_terminal

    def test_valid_transitions(self):
        """Test all valid transitions succeed."""
        test_cases = [
            ("created", "submitted"),
            ("submitted", "acked"),
            ("submitted", "filled"),
            ("submitted", "rejected"),
            ("submitted", "cancel_requested"),
            ("acked", "filled"),
            ("acked", "partial_fill"),
            ("acked", "cancel_requested"),
            ("acked", "expired"),
            ("partial_fill", "filled"),
            ("partial_fill", "cancel_requested"),
            ("cancel_requested", "cancelled"),
            ("cancel_requested", "filled"),
            ("cancelled", "replaced"),
            ("error", "submitted"),
        ]
        for from_state, to_state in test_cases:
            intent = OrderIntent(status=from_state)
            assert intent.can_transition_to(to_state), f"{from_state} → {to_state} should be valid"
            intent.transition(to_state)
            assert intent.status == to_state

    def test_invalid_transitions(self):
        """Test invalid transitions are rejected."""
        test_cases = [
            ("created", "filled"),     # must go through submitted
            ("created", "cancelled"),  # must go through submitted
            ("filled", "cancelled"),   # terminal state
            ("rejected", "submitted"), # terminal state
            ("expired", "submitted"),  # terminal state
            ("cancelled", "submitted"),# cancelled can only go to replaced
        ]
        for from_state, to_state in test_cases:
            intent = OrderIntent(status=from_state)
            assert not intent.can_transition_to(to_state), f"{from_state} → {to_state} should be invalid"
            with pytest.raises(ValueError):
                intent.transition(to_state)

    def test_terminal_states(self):
        """All terminal states are correctly identified."""
        for state in TERMINAL_STATES:
            intent = OrderIntent(status=state)
            assert intent.is_terminal

    def test_non_terminal_states(self):
        non_terminal = {"created", "submitted", "acked", "partial_fill", "cancel_requested", "error"}
        for state in non_terminal:
            intent = OrderIntent(status=state)
            assert not intent.is_terminal

    def test_transition_updates_timestamp(self):
        intent = OrderIntent()
        old_time = intent.updated_at
        import time
        time.sleep(0.01)
        intent.transition("submitted")
        assert intent.updated_at > old_time

    def test_all_states_covered_in_transitions(self):
        """Every state should have an entry in VALID_TRANSITIONS."""
        all_states = {
            "created", "submitted", "acked", "partial_fill",
            "cancel_requested", "cancelled", "replaced",
            "filled", "rejected", "expired", "error",
        }
        assert set(VALID_TRANSITIONS.keys()) == all_states


class TestOrderIntentFields:
    """Test intent field defaults and properties."""

    def test_default_values(self):
        intent = OrderIntent()
        assert intent.id  # UUID generated
        assert intent.idempotency_key == ""
        assert intent.symbol == ""
        assert intent.side == ""
        assert intent.order_type == "limit"
        assert intent.qty is None
        assert intent.notional is None
        assert intent.limit_price is None
        assert intent.engine == ""
        assert intent.mode == "paper"
        assert intent.broker_order_id is None
        assert intent.fill_price is None
        assert intent.fill_qty is None
        assert intent.metadata == {}

    def test_custom_values(self):
        intent = OrderIntent(
            symbol="BTC-USD",
            side="buy",
            qty=0.5,
            limit_price=50000.0,
            engine="edge_factory",
            mode="live",
        )
        assert intent.symbol == "BTC-USD"
        assert intent.side == "buy"
        assert intent.qty == 0.5
        assert intent.limit_price == 50000.0
        assert intent.engine == "edge_factory"
        assert intent.mode == "live"
