"""Tests for Circuit Breaker risk management."""
import pytest
from services.risk.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState


class TestCircuitBreaker:
    """Test circuit breaker risk guards."""

    def test_initial_state_closed(self):
        """Circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker(starting_equity=150.0)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_trading_allowed

    def test_can_trade_basic(self):
        """Basic trade should be allowed in CLOSED state."""
        breaker = CircuitBreaker(starting_equity=150.0)
        assert breaker.can_trade("BTC-USD", notional=10.0)

    def test_per_symbol_exposure_cap(self):
        """Should block trades exceeding per-symbol limit."""
        config = CircuitConfig(max_per_symbol_notional=20.0)
        breaker = CircuitBreaker(starting_equity=150.0, config=config)

        breaker.update_position("BTC-USD", 15.0)
        assert not breaker.can_trade("BTC-USD", notional=10.0)  # 15+10=25 > 20

    def test_total_exposure_cap(self):
        """Should block trades exceeding total portfolio limit."""
        config = CircuitConfig(max_total_notional=50.0)
        breaker = CircuitBreaker(starting_equity=150.0, config=config)

        breaker.update_position("BTC-USD", 20.0)
        breaker.update_position("ETH-USD", 20.0)
        assert not breaker.can_trade("SOL-USD", notional=15.0)  # 20+20+15=55 > 50

    def test_consecutive_losses_trip(self):
        """Should trip after N consecutive losing trades."""
        config = CircuitConfig(max_consecutive_losses=3)
        breaker = CircuitBreaker(starting_equity=150.0, config=config)

        breaker.record_trade_result(pnl=-1.0)
        assert breaker.state == CircuitState.CLOSED

        breaker.record_trade_result(pnl=-1.0)
        assert breaker.state == CircuitState.CLOSED

        breaker.record_trade_result(pnl=-1.0)
        assert breaker.state == CircuitState.OPEN
        assert not breaker.is_trading_allowed

    def test_winning_trade_resets_consecutive_losses(self):
        """A winning trade should reset the consecutive loss counter."""
        config = CircuitConfig(max_consecutive_losses=3)
        breaker = CircuitBreaker(starting_equity=150.0, config=config)

        breaker.record_trade_result(pnl=-1.0)
        breaker.record_trade_result(pnl=-1.0)
        breaker.record_trade_result(pnl=0.50)  # Win resets counter
        breaker.record_trade_result(pnl=-1.0)
        breaker.record_trade_result(pnl=-1.0)

        assert breaker.state == CircuitState.CLOSED  # Not tripped

    def test_daily_loss_limit(self):
        """Should trip when daily realized losses exceed limit."""
        config = CircuitConfig(daily_loss_limit_pct=3.0)
        breaker = CircuitBreaker(starting_equity=100.0, config=config)

        breaker.record_trade_result(pnl=-2.0)
        assert breaker.state == CircuitState.CLOSED

        breaker.record_trade_result(pnl=-1.5)  # Total: -3.5 = 3.5% > 3%
        assert breaker.state == CircuitState.OPEN

    def test_max_drawdown_trip(self):
        """Should trip when unrealized drawdown exceeds limit."""
        config = CircuitConfig(max_drawdown_pct=5.0)
        breaker = CircuitBreaker(starting_equity=150.0, config=config)

        breaker.update_equity(155.0)  # New peak
        breaker.update_equity(146.0)  # 5.8% drawdown from 155
        assert breaker.state == CircuitState.OPEN

    def test_order_rate_limiting(self):
        """Should block trades when order rate is too high."""
        config = CircuitConfig(max_orders_per_minute=3)
        breaker = CircuitBreaker(starting_equity=150.0, config=config)

        breaker.record_order()
        breaker.record_order()
        breaker.record_order()
        assert not breaker.can_trade("BTC-USD", notional=10.0)

    def test_position_count_limit(self):
        """Should block new positions when at max count."""
        config = CircuitConfig(max_position_count=2)
        breaker = CircuitBreaker(starting_equity=150.0, config=config)

        breaker.update_position("BTC-USD", 10.0)
        breaker.update_position("ETH-USD", 10.0)
        assert not breaker.can_trade("SOL-USD", notional=5.0)  # 3rd position blocked

    def test_existing_position_allowed_at_max(self):
        """Adding to existing position should be allowed even at max count."""
        config = CircuitConfig(max_position_count=2, max_per_symbol_notional=50.0)
        breaker = CircuitBreaker(starting_equity=150.0, config=config)

        breaker.update_position("BTC-USD", 10.0)
        breaker.update_position("ETH-USD", 10.0)
        assert breaker.can_trade("BTC-USD", notional=5.0)  # Existing position OK

    def test_reset_daily(self):
        """Daily reset should clear counters."""
        config = CircuitConfig(max_consecutive_losses=5)
        breaker = CircuitBreaker(starting_equity=150.0, config=config)

        breaker.record_trade_result(pnl=-1.0)
        breaker.record_trade_result(pnl=-1.0)
        breaker.reset_daily(new_starting_equity=148.0)

        assert breaker._consecutive_losses == 0
        assert breaker._daily_realized_pnl == 0.0
        assert breaker.starting_equity == 148.0

    def test_force_close(self):
        """Force close should override OPEN state."""
        breaker = CircuitBreaker(starting_equity=150.0)
        breaker._trip("test", severity="halt")
        assert breaker.state == CircuitState.OPEN

        breaker.force_close()
        assert breaker.state == CircuitState.CLOSED

    def test_summary(self):
        """Summary should contain expected fields."""
        breaker = CircuitBreaker(starting_equity=150.0)
        summary = breaker.summary
        assert "state" in summary
        assert "starting_equity" in summary
        assert "current_equity" in summary
        assert "daily_realized_pnl" in summary
        assert "positions" in summary

    def test_trip_callback(self):
        """Trip should call the on_trip callback."""
        events = []
        breaker = CircuitBreaker(
            starting_equity=150.0,
            config=CircuitConfig(max_consecutive_losses=1),
            on_trip=lambda e: events.append(e),
        )
        breaker.record_trade_result(pnl=-1.0)
        assert len(events) == 1
        assert events[0].severity == "halt"

    def test_remove_position(self):
        """Removing position should work with zero notional."""
        breaker = CircuitBreaker(starting_equity=150.0)
        breaker.update_position("BTC-USD", 10.0)
        assert len(breaker._positions) == 1
        breaker.update_position("BTC-USD", 0.0)
        assert len(breaker._positions) == 0
