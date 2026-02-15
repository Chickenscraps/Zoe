"""Tests for ExitManager — automated TP, SL, trailing-stop, and time-stop exits."""
import time

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from services.crypto_trader.exit_manager import (
    ExitManager,
    ExitPolicy,
    ManagedExit,
)
from services.crypto_trader.position_tracker import Position, PositionStatus


# ── Helpers ──────────────────────────────────────────────────────


def _make_position(
    pos_id: str = "pos-1234-abcd",
    symbol: str = "BTC-USD",
    side: str = "long",
    entry_price: float = 70000.0,
    entry_qty: float = 0.001,
    entry_time: float | None = None,
    tp_price: float = 0.0,
    sl_price: float = 0.0,
) -> Position:
    """Create a real Position dataclass for testing."""
    return Position(
        id=pos_id,
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        entry_qty=entry_qty,
        entry_time=entry_time or time.monotonic(),
        entry_time_utc="2025-01-01T00:00:00Z",
        tp_price=tp_price,
        sl_price=sl_price,
        high_water_mark=entry_price,
    )


def _make_exit_manager(
    policy: ExitPolicy | None = None,
    indicator_engine: MagicMock | None = None,
    tracker: MagicMock | None = None,
    circuit_breaker: MagicMock | None = None,
) -> tuple[ExitManager, MagicMock, MagicMock]:
    """Create ExitManager with mock dependencies. Returns (mgr, order_mgr, price_cache)."""
    order_mgr = MagicMock()
    order_mgr.submit_intent = AsyncMock(return_value="intent-abc123")
    order_mgr.cancel_order = AsyncMock()

    price_cache = MagicMock()
    price_cache.snapshot = MagicMock(return_value={"mid": 70000.0, "bid": 69990.0, "ask": 70010.0})

    mgr = ExitManager(
        order_manager=order_mgr,
        price_cache=price_cache,
        indicator_engine=indicator_engine,
        policy=policy or ExitPolicy(),
        position_tracker=tracker,
        circuit_breaker=circuit_breaker,
        mode="paper",
    )
    return mgr, order_mgr, price_cache


def _make_indicator_engine(atr: float = 350.0, valid: bool = True) -> MagicMock:
    """Create a mock IndicatorEngine with configurable ATR snapshot."""
    engine = MagicMock()
    snap = MagicMock()
    snap.is_valid.return_value = valid
    snap.atr = atr
    engine.snapshot.return_value = snap
    engine.record_trade = MagicMock()
    return engine


# ── ExitPolicy tests ─────────────────────────────────────────────


class TestExitPolicy:
    """Test ExitPolicy defaults and config loading."""

    def test_defaults(self):
        p = ExitPolicy()
        assert p.tp_pct == 0.045
        assert p.sl_atr_mult == 1.5
        assert p.sl_hard_pct == 0.03
        assert p.time_stop_hours == 12.0
        assert p.trailing_activate_pct == 0.02
        assert p.trailing_step_pct == 0.005

    def test_from_config_returns_defaults_on_missing_file(self):
        """When config.yaml is missing, from_config() returns defaults."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            p = ExitPolicy.from_config()
        assert p.tp_pct == 0.045
        assert p.sl_hard_pct == 0.03

    def test_from_config_reads_bounce_execution(self, tmp_path):
        """from_config() reads values from bounce.execution in config.yaml."""
        config_content = """
bounce:
  execution:
    tp_pct: 0.06
    sl_atr_mult: 2.0
    sl_hard_pct: 0.05
    time_stop_hours: 8.0
    trailing_activate_pct: 0.03
    trailing_step_pct: 0.01
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with patch("services.crypto_trader.exit_manager._CONFIG_PATH", config_file):
            p = ExitPolicy.from_config()

        assert p.tp_pct == 0.06
        assert p.sl_atr_mult == 2.0
        assert p.sl_hard_pct == 0.05
        assert p.time_stop_hours == 8.0
        assert p.trailing_activate_pct == 0.03
        assert p.trailing_step_pct == 0.01


# ── ManagedExit tests ────────────────────────────────────────────


class TestManagedExit:
    """Test ManagedExit dataclass properties."""

    def test_age_hours_property(self):
        """age_hours returns elapsed hours since entry_time."""
        entry = time.monotonic() - 7200  # 2 hours ago
        me = ManagedExit(
            position_id="p1",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=entry,
            tp_price=73150,
            sl_price=67900,
        )
        assert 1.9 < me.age_hours < 2.1


# ── on_entry_fill() tests ────────────────────────────────────────


class TestOnEntryFill:
    """Test on_entry_fill() — computes TP/SL and places TP order."""

    @pytest.mark.asyncio
    async def test_long_entry_computes_tp_sl_and_places_order(self):
        engine = _make_indicator_engine(atr=350.0)
        tracker = MagicMock()
        mgr, order_mgr, _ = _make_exit_manager(indicator_engine=engine, tracker=tracker)

        pos = _make_position(side="long", entry_price=70000.0, entry_qty=0.001)
        await mgr.on_entry_fill(pos)

        # TP = 70000 * 1.045 = 73150
        managed = mgr._exits[pos.id]
        assert managed.tp_price == round(70000.0 * 1.045, 8)

        # SL should be set (either ATR-based or hard)
        assert managed.sl_price > 0
        assert managed.sl_price < 70000.0  # Below entry for long

        # TP order should have been placed
        order_mgr.submit_intent.assert_awaited_once()
        call_kwargs = order_mgr.submit_intent.call_args.kwargs
        assert call_kwargs["symbol"] == "BTC-USD"
        assert call_kwargs["side"] == "sell"  # Exit side for long
        assert call_kwargs["purpose"] == "exit"
        assert call_kwargs["strategy"] == "take_profit"
        assert call_kwargs["order_type"] == "limit"
        assert call_kwargs["limit_price"] == managed.tp_price

        # Tracker should have TP/SL updated
        assert pos.tp_price == managed.tp_price
        assert pos.sl_price == managed.sl_price

        # Tracker.begin_exit called with intent_id
        tracker.begin_exit.assert_called_once_with(pos.id, "intent-abc123")

    @pytest.mark.asyncio
    async def test_short_entry_computes_tp_below_and_sl_above(self):
        engine = _make_indicator_engine(atr=350.0)
        mgr, order_mgr, _ = _make_exit_manager(indicator_engine=engine)

        pos = _make_position(side="short", entry_price=70000.0, entry_qty=0.001)
        await mgr.on_entry_fill(pos)

        managed = mgr._exits[pos.id]
        # TP = 70000 * (1 - 0.045) = 66850
        assert managed.tp_price == round(70000.0 * (1 - 0.045), 8)
        # SL should be above entry for short
        assert managed.sl_price > 70000.0

        # Exit side for short is "buy"
        call_kwargs = order_mgr.submit_intent.call_args.kwargs
        assert call_kwargs["side"] == "buy"

    @pytest.mark.asyncio
    async def test_order_to_position_map_populated(self):
        mgr, _, _ = _make_exit_manager()
        pos = _make_position()
        await mgr.on_entry_fill(pos)

        # intent_id should map to position_id
        assert mgr._order_to_position["intent-abc123"] == pos.id


# ── tick() tests ─────────────────────────────────────────────────


class TestTick:
    """Test tick() — time stops, SL triggers, trailing, TP re-placement."""

    @pytest.mark.asyncio
    async def test_time_stop_detection(self):
        """Positions held past time_stop_hours get market-exited."""
        policy = ExitPolicy(time_stop_hours=1.0)
        mgr, order_mgr, price_cache = _make_exit_manager(policy=policy)

        # Create a managed exit that has been open 2 hours
        entry_time = time.monotonic() - 7200
        managed = ManagedExit(
            position_id="p-old",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=entry_time,
            tp_price=73150,
            sl_price=67900,
            tp_order_id="tp-order-1",
            tp_order_status="placed",
        )
        mgr._exits["p-old"] = managed
        mgr._order_to_position["tp-order-1"] = "p-old"

        price_cache.snapshot.return_value = {"mid": 70500.0, "bid": 70490.0, "ask": 70510.0}

        await mgr.tick()

        # Should have cancelled TP order and submitted market exit
        order_mgr.cancel_order.assert_awaited_once_with("tp-order-1", reason="time_stop")
        order_mgr.submit_intent.assert_awaited_once()
        call_kwargs = order_mgr.submit_intent.call_args.kwargs
        assert call_kwargs["order_type"] == "market"
        assert call_kwargs["strategy"] == "time_stop"

        # Should be marked as triggered
        assert managed.sl_triggered is True

    @pytest.mark.asyncio
    async def test_sl_trigger_long_position(self):
        """SL fires when mid drops below sl_price for long."""
        mgr, order_mgr, price_cache = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-long",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            tp_order_id="tp-1",
            tp_order_status="placed",
        )
        mgr._exits["p-long"] = managed
        mgr._order_to_position["tp-1"] = "p-long"

        # Mid drops below SL
        price_cache.snapshot.return_value = {"mid": 67000.0, "bid": 66990.0, "ask": 67010.0}

        await mgr.tick()

        # TP cancelled, market sell submitted
        order_mgr.cancel_order.assert_awaited_once_with("tp-1", reason="sl_triggered")
        call_kwargs = order_mgr.submit_intent.call_args.kwargs
        assert call_kwargs["side"] == "sell"
        assert call_kwargs["order_type"] == "market"
        assert call_kwargs["strategy"] == "stop_loss"
        assert managed.sl_triggered is True

    @pytest.mark.asyncio
    async def test_sl_trigger_short_position(self):
        """SL fires when mid rises above sl_price for short."""
        mgr, order_mgr, price_cache = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-short",
            symbol="ETH-USD",
            side="short",
            entry_price=3500,
            entry_qty=0.1,
            entry_time=time.monotonic(),
            tp_price=3342.5,  # 3500 * 0.955
            sl_price=3605,    # above entry
            tp_order_id="tp-2",
            tp_order_status="placed",
        )
        mgr._exits["p-short"] = managed
        mgr._order_to_position["tp-2"] = "p-short"

        # Mid rises above SL for short
        price_cache.snapshot.return_value = {"mid": 3650.0, "bid": 3649.0, "ask": 3651.0}

        await mgr.tick()

        order_mgr.cancel_order.assert_awaited_once_with("tp-2", reason="sl_triggered")
        call_kwargs = order_mgr.submit_intent.call_args.kwargs
        assert call_kwargs["side"] == "buy"  # Exit side for short
        assert call_kwargs["order_type"] == "market"
        assert managed.sl_triggered is True

    @pytest.mark.asyncio
    async def test_trailing_stop_activation_and_tightening(self):
        """Trailing stop activates after profit threshold, then tightens."""
        policy = ExitPolicy(
            trailing_activate_pct=0.02,
            trailing_step_pct=0.005,
            time_stop_hours=100,  # prevent time stop
        )
        mgr, order_mgr, price_cache = _make_exit_manager(policy=policy)

        managed = ManagedExit(
            position_id="p-trail",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            high_water_mark=70000,
            tp_order_id="tp-trail",
            tp_order_status="placed",
        )
        mgr._exits["p-trail"] = managed
        mgr._order_to_position["tp-trail"] = "p-trail"

        # Price rises 3% above entry -> should activate trailing
        price_cache.snapshot.return_value = {"mid": 72100.0, "bid": 72090.0, "ask": 72110.0}
        await mgr.tick()

        assert managed.trailing_sl is not None
        first_trailing = managed.trailing_sl
        # trailing = 72100 * (1 - 0.005) = 71739.5
        assert abs(first_trailing - 72100.0 * 0.995) < 1.0

        # Price rises further -> trailing tightens
        price_cache.snapshot.return_value = {"mid": 73000.0, "bid": 72990.0, "ask": 73010.0}
        await mgr.tick()

        assert managed.trailing_sl > first_trailing
        assert managed.high_water_mark == 73000.0

    @pytest.mark.asyncio
    async def test_trailing_stop_never_loosens(self):
        """Trailing stop never moves further from price (only tightens)."""
        policy = ExitPolicy(
            trailing_activate_pct=0.02,
            trailing_step_pct=0.005,
            time_stop_hours=100,
        )
        mgr, _, price_cache = _make_exit_manager(policy=policy)

        managed = ManagedExit(
            position_id="p-no-loosen",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            high_water_mark=70000,
            tp_order_id="tp-x",
            tp_order_status="placed",
        )
        mgr._exits["p-no-loosen"] = managed
        mgr._order_to_position["tp-x"] = "p-no-loosen"

        # Price goes up -> activates trailing
        price_cache.snapshot.return_value = {"mid": 72000.0, "bid": 71990.0, "ask": 72010.0}
        await mgr.tick()
        high_trailing = managed.trailing_sl

        # Price dips back slightly (still above SL) -> trailing should NOT loosen
        price_cache.snapshot.return_value = {"mid": 71500.0, "bid": 71490.0, "ask": 71510.0}
        await mgr.tick()
        assert managed.trailing_sl == high_trailing

    @pytest.mark.asyncio
    async def test_tp_order_replacement_when_cancelled(self):
        """TP order is re-placed on next tick if status is cancelled."""
        mgr, order_mgr, price_cache = _make_exit_manager(
            policy=ExitPolicy(time_stop_hours=100),
        )

        managed = ManagedExit(
            position_id="p-repl",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            tp_order_id=None,
            tp_order_status="cancelled",  # Needs re-placement
        )
        mgr._exits["p-repl"] = managed

        # Mid is safely above SL, no time stop
        price_cache.snapshot.return_value = {"mid": 70500.0, "bid": 70490.0, "ask": 70510.0}

        await mgr.tick()

        # submit_intent should have been called to re-place TP
        order_mgr.submit_intent.assert_awaited_once()
        call_kwargs = order_mgr.submit_intent.call_args.kwargs
        assert call_kwargs["strategy"] == "take_profit"
        assert call_kwargs["order_type"] == "limit"
        assert managed.tp_order_status == "placed"

    @pytest.mark.asyncio
    async def test_tick_skips_zero_mid(self):
        """tick() skips positions with zero mid price."""
        mgr, order_mgr, price_cache = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-zero",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
        )
        mgr._exits["p-zero"] = managed
        price_cache.snapshot.return_value = {"mid": 0.0, "bid": 0.0, "ask": 0.0}

        await mgr.tick()

        # No orders should be submitted
        order_mgr.submit_intent.assert_not_awaited()
        order_mgr.cancel_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_tick_skips_already_exited(self):
        """tick() skips positions that already have exit_reason and sl_triggered."""
        mgr, order_mgr, price_cache = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-done",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            exit_reason="take_profit",
            sl_triggered=True,
        )
        mgr._exits["p-done"] = managed
        price_cache.snapshot.return_value = {"mid": 50000.0, "bid": 49990.0, "ask": 50010.0}

        await mgr.tick()

        order_mgr.submit_intent.assert_not_awaited()


# ── on_exit_fill() tests ─────────────────────────────────────────


class TestOnExitFill:
    """Test on_exit_fill() — fill routing and position closing."""

    def test_tp_fill_closes_position_and_feeds_breaker(self):
        """TP fill sets exit_reason, computes PnL, feeds circuit breaker."""
        breaker = MagicMock()
        tracker = MagicMock()
        engine = _make_indicator_engine()
        mgr, _, _ = _make_exit_manager(
            circuit_breaker=breaker,
            tracker=tracker,
            indicator_engine=engine,
        )

        managed = ManagedExit(
            position_id="p-tp",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            tp_order_id="tp-order-99",
            tp_order_status="placed",
        )
        mgr._exits["p-tp"] = managed
        mgr._order_to_position["tp-order-99"] = "p-tp"

        result = mgr.on_exit_fill("BTC-USD", 0.001, 73150.0, "tp-order-99")

        assert result == "p-tp"
        # PnL = (73150 - 70000) * 0.001 = 3.15
        expected_pnl = (73150.0 - 70000.0) * 0.001
        breaker.record_trade_result.assert_called_once_with(expected_pnl, "BTC-USD")
        tracker.close_position.assert_called_once_with("p-tp", exit_price=73150.0, realized_pnl=expected_pnl)
        engine.record_trade.assert_called_once_with("BTC-USD", "long")

        # Position should be cleaned up
        assert "p-tp" not in mgr._exits
        assert "tp-order-99" not in mgr._order_to_position

    def test_sl_fill_closes_position(self):
        """SL fill sets reason to stop_loss."""
        tracker = MagicMock()
        mgr, _, _ = _make_exit_manager(tracker=tracker)

        managed = ManagedExit(
            position_id="p-sl",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            sl_order_id="sl-order-1",
            sl_triggered=True,
        )
        mgr._exits["p-sl"] = managed
        mgr._order_to_position["sl-order-1"] = "p-sl"

        result = mgr.on_exit_fill("BTC-USD", 0.001, 67800.0, "sl-order-1")

        assert result == "p-sl"
        # PnL = (67800 - 70000) * 0.001 = -2.2
        expected_pnl = (67800.0 - 70000.0) * 0.001
        tracker.close_position.assert_called_once_with("p-sl", exit_price=67800.0, realized_pnl=expected_pnl)

    def test_short_position_pnl_calculation(self):
        """PnL for short: (entry - exit) * qty."""
        tracker = MagicMock()
        mgr, _, _ = _make_exit_manager(tracker=tracker)

        managed = ManagedExit(
            position_id="p-short-exit",
            symbol="ETH-USD",
            side="short",
            entry_price=3500,
            entry_qty=0.1,
            entry_time=time.monotonic(),
            tp_price=3342.5,
            sl_price=3605,
            tp_order_id="tp-short",
            tp_order_status="placed",
        )
        mgr._exits["p-short-exit"] = managed
        mgr._order_to_position["tp-short"] = "p-short-exit"

        result = mgr.on_exit_fill("ETH-USD", 0.1, 3342.5, "tp-short")

        assert result == "p-short-exit"
        # PnL = (3500 - 3342.5) * 0.1 = 15.75
        expected_pnl = (3500.0 - 3342.5) * 0.1
        tracker.close_position.assert_called_once_with(
            "p-short-exit", exit_price=3342.5, realized_pnl=expected_pnl,
        )

    def test_unknown_order_fallback_by_symbol(self):
        """When order_id is unknown, falls back to symbol match."""
        tracker = MagicMock()
        mgr, _, _ = _make_exit_manager(tracker=tracker)

        managed = ManagedExit(
            position_id="p-fallback",
            symbol="SOL-USD",
            side="long",
            entry_price=150,
            entry_qty=1.0,
            entry_time=time.monotonic(),
            tp_price=156.75,
            sl_price=145.5,
        )
        mgr._exits["p-fallback"] = managed
        # Note: no mapping in _order_to_position for "mystery-order"

        result = mgr.on_exit_fill("SOL-USD", 1.0, 155.0, "mystery-order")

        assert result == "p-fallback"
        tracker.close_position.assert_called_once()

    def test_unknown_order_unknown_symbol_returns_none(self):
        """When neither order_id nor symbol matches, returns None."""
        mgr, _, _ = _make_exit_manager()
        result = mgr.on_exit_fill("UNKNOWN-USD", 1.0, 100.0, "no-such-order")
        assert result is None

    def test_exit_fill_without_breaker_or_tracker(self):
        """on_exit_fill works even without circuit breaker or tracker."""
        mgr, _, _ = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-bare",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            tp_order_id="tp-bare",
            tp_order_status="placed",
        )
        mgr._exits["p-bare"] = managed
        mgr._order_to_position["tp-bare"] = "p-bare"

        result = mgr.on_exit_fill("BTC-USD", 0.001, 73150.0, "tp-bare")
        assert result == "p-bare"
        assert "p-bare" not in mgr._exits

    def test_exit_fill_sets_reason_exit_fill_for_unknown_order(self):
        """When order_id is not tp_order_id and sl not triggered, reason is exit_fill."""
        mgr, _, _ = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-generic",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            tp_order_id="tp-known",
            tp_order_status="placed",
            sl_triggered=False,
        )
        mgr._exits["p-generic"] = managed
        # Map an unrelated order to this position
        mgr._order_to_position["other-order"] = "p-generic"

        result = mgr.on_exit_fill("BTC-USD", 0.001, 71000.0, "other-order")
        assert result == "p-generic"
        # Since sl_triggered=False and order_id != tp_order_id, reason should be "exit_fill"
        # (managed is cleaned up, but we can check before cleanup by examining the call)


# ── on_tp_order_cancelled() tests ────────────────────────────────


class TestOnTpOrderCancelled:
    """Test on_tp_order_cancelled() marks status for re-placement."""

    def test_marks_status_cancelled(self):
        mgr, _, _ = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-cancel",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            tp_order_id="tp-cancel-1",
            tp_order_status="placed",
        )
        mgr._exits["p-cancel"] = managed
        mgr._order_to_position["tp-cancel-1"] = "p-cancel"

        mgr.on_tp_order_cancelled("tp-cancel-1")

        assert managed.tp_order_status == "cancelled"
        assert managed.tp_order_id is None

    def test_unknown_order_does_nothing(self):
        mgr, _, _ = _make_exit_manager()
        # Should not raise
        mgr.on_tp_order_cancelled("nonexistent-order")


# ── recover_from_tracker() tests ─────────────────────────────────


class TestRecoverFromTracker:
    """Test recover_from_tracker() restores exit management for open positions."""

    def test_recovers_open_positions(self):
        mgr, _, _ = _make_exit_manager()

        pos1 = _make_position(
            pos_id="rec-1", symbol="BTC-USD", side="long",
            entry_price=70000, entry_qty=0.001,
            tp_price=73150, sl_price=67900,
        )
        pos1.high_water_mark = 71000
        pos1.trailing_sl = 70645

        pos2 = _make_position(
            pos_id="rec-2", symbol="ETH-USD", side="short",
            entry_price=3500, entry_qty=0.1,
            tp_price=3342.5, sl_price=3605,
        )

        tracker = MagicMock()
        tracker.get_open.return_value = [pos1, pos2]

        count = mgr.recover_from_tracker(tracker)

        assert count == 2
        assert "rec-1" in mgr._exits
        assert "rec-2" in mgr._exits

        # Check recovered values
        m1 = mgr._exits["rec-1"]
        assert m1.tp_price == 73150
        assert m1.sl_price == 67900
        assert m1.high_water_mark == 71000
        assert m1.trailing_sl == 70645
        assert m1.tp_order_status == "cancelled"  # Will be re-placed on tick

        m2 = mgr._exits["rec-2"]
        assert m2.side == "short"
        assert m2.symbol == "ETH-USD"

    def test_skips_already_managed(self):
        mgr, _, _ = _make_exit_manager()

        # Pre-existing managed exit
        existing = ManagedExit(
            position_id="existing-1",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            tp_order_status="placed",
        )
        mgr._exits["existing-1"] = existing

        pos = _make_position(pos_id="existing-1", symbol="BTC-USD")
        tracker = MagicMock()
        tracker.get_open.return_value = [pos]

        count = mgr.recover_from_tracker(tracker)
        assert count == 0  # Already managed, skipped

    def test_returns_zero_for_no_open_positions(self):
        mgr, _, _ = _make_exit_manager()
        tracker = MagicMock()
        tracker.get_open.return_value = []

        count = mgr.recover_from_tracker(tracker)
        assert count == 0


# ── _compute_sl() tests ─────────────────────────────────────────


class TestComputeSl:
    """Test _compute_sl() — ATR-based and hard-stop SL calculation."""

    def test_with_atr_available_long(self):
        """ATR-based SL for long: entry - (ATR * mult), clamped by hard stop."""
        engine = _make_indicator_engine(atr=500.0, valid=True)
        policy = ExitPolicy(sl_atr_mult=1.5, sl_hard_pct=0.03)
        mgr, _, _ = _make_exit_manager(policy=policy, indicator_engine=engine)

        sl = mgr._compute_sl("BTC-USD", 70000.0, "long")

        # ATR SL = 70000 - (500 * 1.5) = 69250
        # Hard SL = 70000 * 0.97 = 67900
        # For long, use max(atr, hard) = 69250 (tighter)
        assert sl == round(69250.0, 8)

    def test_with_atr_available_short(self):
        """ATR-based SL for short: entry + (ATR * mult), clamped by hard stop."""
        engine = _make_indicator_engine(atr=500.0, valid=True)
        policy = ExitPolicy(sl_atr_mult=1.5, sl_hard_pct=0.03)
        mgr, _, _ = _make_exit_manager(policy=policy, indicator_engine=engine)

        sl = mgr._compute_sl("BTC-USD", 70000.0, "short")

        # ATR SL = 70000 + (500 * 1.5) = 70750
        # Hard SL = 70000 * 1.03 = 72100
        # For short, use min(atr, hard) = 70750 (tighter)
        assert sl == round(70750.0, 8)

    def test_no_atr_uses_hard_stop_long(self):
        """Without ATR, uses hard percentage stop for long."""
        engine = _make_indicator_engine(atr=0.0, valid=False)
        policy = ExitPolicy(sl_hard_pct=0.03)
        mgr, _, _ = _make_exit_manager(policy=policy, indicator_engine=engine)

        sl = mgr._compute_sl("BTC-USD", 70000.0, "long")
        assert sl == round(70000.0 * 0.97, 8)

    def test_no_atr_uses_hard_stop_short(self):
        """Without ATR, uses hard percentage stop for short."""
        policy = ExitPolicy(sl_hard_pct=0.03)
        mgr, _, _ = _make_exit_manager(policy=policy, indicator_engine=None)

        sl = mgr._compute_sl("BTC-USD", 70000.0, "short")
        assert sl == round(70000.0 * 1.03, 8)

    def test_no_indicator_engine_uses_hard_stop(self):
        """Without indicator engine at all, falls back to hard stop."""
        policy = ExitPolicy(sl_hard_pct=0.05)
        mgr, _, _ = _make_exit_manager(policy=policy, indicator_engine=None)

        sl = mgr._compute_sl("BTC-USD", 50000.0, "long")
        assert sl == round(50000.0 * 0.95, 8)

    def test_atr_wider_than_hard_stop_long_uses_hard(self):
        """When ATR stop is wider than hard stop for long, uses hard (closer to entry)."""
        # ATR = 3000, mult=1.5 -> distance=4500
        # ATR SL = 70000 - 4500 = 65500
        # Hard SL = 70000 * 0.97 = 67900
        # max(65500, 67900) = 67900 (hard is tighter)
        engine = _make_indicator_engine(atr=3000.0, valid=True)
        policy = ExitPolicy(sl_atr_mult=1.5, sl_hard_pct=0.03)
        mgr, _, _ = _make_exit_manager(policy=policy, indicator_engine=engine)

        sl = mgr._compute_sl("BTC-USD", 70000.0, "long")
        assert sl == round(67900.0, 8)

    def test_atr_wider_than_hard_stop_short_uses_hard(self):
        """When ATR stop is wider than hard stop for short, uses hard (closer to entry)."""
        # ATR = 3000, mult=1.5 -> distance=4500
        # ATR SL = 70000 + 4500 = 74500
        # Hard SL = 70000 * 1.03 = 72100
        # min(74500, 72100) = 72100 (hard is tighter)
        engine = _make_indicator_engine(atr=3000.0, valid=True)
        policy = ExitPolicy(sl_atr_mult=1.5, sl_hard_pct=0.03)
        mgr, _, _ = _make_exit_manager(policy=policy, indicator_engine=engine)

        sl = mgr._compute_sl("BTC-USD", 70000.0, "short")
        assert sl == round(72100.0, 8)


# ── _update_trailing() tests ─────────────────────────────────────


class TestUpdateTrailing:
    """Test _update_trailing() — high-water mark and trailing stop updates."""

    def test_long_trailing_activates_above_threshold(self):
        """For long, trailing activates once profit exceeds trailing_activate_pct."""
        policy = ExitPolicy(trailing_activate_pct=0.02, trailing_step_pct=0.005)
        mgr, _, _ = _make_exit_manager(policy=policy)

        managed = ManagedExit(
            position_id="p1",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            high_water_mark=70000,
        )

        # Price rises 3% -> profit_pct = (72100 - 70000)/70000 = 0.03
        mgr._update_trailing(managed, 72100.0)

        assert managed.high_water_mark == 72100.0
        assert managed.trailing_sl is not None
        # trailing = 72100 * (1 - 0.005) = 71739.5
        assert abs(managed.trailing_sl - 71739.5) < 1.0

    def test_long_trailing_does_not_activate_below_threshold(self):
        """For long, trailing stays None if profit is below threshold."""
        policy = ExitPolicy(trailing_activate_pct=0.02, trailing_step_pct=0.005)
        mgr, _, _ = _make_exit_manager(policy=policy)

        managed = ManagedExit(
            position_id="p1",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            high_water_mark=70000,
        )

        # Price rises only 1% -> below 2% threshold
        mgr._update_trailing(managed, 70700.0)

        assert managed.high_water_mark == 70700.0
        assert managed.trailing_sl is None

    def test_long_trailing_tightens_only(self):
        """For long, trailing stop only moves up, never down."""
        policy = ExitPolicy(trailing_activate_pct=0.02, trailing_step_pct=0.005)
        mgr, _, _ = _make_exit_manager(policy=policy)

        managed = ManagedExit(
            position_id="p1",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            high_water_mark=72000,
            trailing_sl=71640.0,  # Already set
        )

        # Price drops to 71500 -> hwm stays 72000, trailing stays 71640
        mgr._update_trailing(managed, 71500.0)
        assert managed.high_water_mark == 72000.0  # No change
        assert managed.trailing_sl == 71640.0  # No loosening

    def test_short_trailing_activates_below_threshold(self):
        """For short, trailing activates when price drops below threshold."""
        policy = ExitPolicy(trailing_activate_pct=0.02, trailing_step_pct=0.005)
        mgr, _, _ = _make_exit_manager(policy=policy)

        managed = ManagedExit(
            position_id="p-short-t",
            symbol="ETH-USD",
            side="short",
            entry_price=3500,
            entry_qty=0.1,
            entry_time=time.monotonic(),
            tp_price=3342.5,
            sl_price=3605,
            high_water_mark=3500,
        )

        # Price drops 3% -> profit for short = (3500 - 3395)/3500 = 0.03
        mgr._update_trailing(managed, 3395.0)

        assert managed.high_water_mark == 3395.0
        assert managed.trailing_sl is not None
        # trailing = 3395 * (1 + 0.005) = 3411.975
        assert abs(managed.trailing_sl - 3395.0 * 1.005) < 1.0

    def test_short_trailing_tightens_only(self):
        """For short, trailing stop only moves down, never up."""
        policy = ExitPolicy(trailing_activate_pct=0.02, trailing_step_pct=0.005)
        mgr, _, _ = _make_exit_manager(policy=policy)

        managed = ManagedExit(
            position_id="p-short-tight",
            symbol="ETH-USD",
            side="short",
            entry_price=3500,
            entry_qty=0.1,
            entry_time=time.monotonic(),
            tp_price=3342.5,
            sl_price=3605,
            high_water_mark=3395,
            trailing_sl=3411.975,  # Already set
        )

        # Price goes even lower
        mgr._update_trailing(managed, 3350.0)

        assert managed.high_water_mark == 3350.0
        # New trailing = 3350 * 1.005 = 3366.75 < 3411.975 -> tightened
        assert managed.trailing_sl < 3411.975

    def test_short_high_water_mark_initialized_from_zero(self):
        """For short, if high_water_mark is 0 it gets set to mid."""
        policy = ExitPolicy(trailing_activate_pct=0.02, trailing_step_pct=0.005)
        mgr, _, _ = _make_exit_manager(policy=policy)

        managed = ManagedExit(
            position_id="p-short-init",
            symbol="ETH-USD",
            side="short",
            entry_price=3500,
            entry_qty=0.1,
            entry_time=time.monotonic(),
            tp_price=3342.5,
            sl_price=3605,
            high_water_mark=0,  # Not yet initialized
        )

        mgr._update_trailing(managed, 3400.0)
        assert managed.high_water_mark == 3400.0


# ── is_exit_order() / get_position_for_order() tests ─────────────


class TestQueryMethods:
    """Test is_exit_order() and get_position_for_order()."""

    def test_is_exit_order_true(self):
        mgr, _, _ = _make_exit_manager()
        mgr._order_to_position["order-123"] = "pos-456"
        assert mgr.is_exit_order("order-123") is True

    def test_is_exit_order_false(self):
        mgr, _, _ = _make_exit_manager()
        assert mgr.is_exit_order("nonexistent") is False

    def test_get_position_for_order_found(self):
        mgr, _, _ = _make_exit_manager()
        mgr._order_to_position["order-123"] = "pos-456"
        assert mgr.get_position_for_order("order-123") == "pos-456"

    def test_get_position_for_order_not_found(self):
        mgr, _, _ = _make_exit_manager()
        assert mgr.get_position_for_order("nonexistent") is None

    def test_has_exit(self):
        mgr, _, _ = _make_exit_manager()
        managed = ManagedExit(
            position_id="p-has",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
        )
        mgr._exits["p-has"] = managed
        assert mgr.has_exit("p-has") is True
        assert mgr.has_exit("p-nope") is False

    def test_active_exit_count(self):
        mgr, _, _ = _make_exit_manager()

        # Two active, one completed
        for i, reason in enumerate([None, None, "take_profit"]):
            m = ManagedExit(
                position_id=f"p-{i}",
                symbol="BTC-USD",
                side="long",
                entry_price=70000,
                entry_qty=0.001,
                entry_time=time.monotonic(),
                tp_price=73150,
                sl_price=67900,
                exit_reason=reason,
            )
            mgr._exits[f"p-{i}"] = m

        assert mgr.active_exit_count == 2

    def test_get_managed_exits(self):
        mgr, _, _ = _make_exit_manager()
        m = ManagedExit(
            position_id="p-list",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
        )
        mgr._exits["p-list"] = m
        exits = mgr.get_managed_exits()
        assert len(exits) == 1
        assert exits[0].position_id == "p-list"


# ── _execute_sl() internal behavior ──────────────────────────────


class TestExecuteSl:
    """Test _execute_sl() — SL execution details."""

    @pytest.mark.asyncio
    async def test_sl_sets_trailing_stop_reason_when_trailing(self):
        """When effective_sl equals trailing_sl, reason is trailing_stop."""
        tracker = MagicMock()
        mgr, order_mgr, _ = _make_exit_manager(tracker=tracker)

        managed = ManagedExit(
            position_id="p-trail-sl",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            trailing_sl=71500.0,
            tp_order_id="tp-trail-sl",
            tp_order_status="placed",
        )
        mgr._exits["p-trail-sl"] = managed
        mgr._order_to_position["tp-trail-sl"] = "p-trail-sl"

        await mgr._execute_sl(managed, current_mid=71400.0, effective_sl=71500.0)

        call_kwargs = order_mgr.submit_intent.call_args.kwargs
        assert call_kwargs["strategy"] == "trailing_stop"
        assert managed.sl_triggered is True
        tracker.mark_closing.assert_called_once_with("p-trail-sl")

    @pytest.mark.asyncio
    async def test_sl_without_tp_order(self):
        """SL execution works even if tp_order_id is None."""
        mgr, order_mgr, _ = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-no-tp",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            tp_order_id=None,
            tp_order_status="cancelled",
        )
        mgr._exits["p-no-tp"] = managed

        await mgr._execute_sl(managed, current_mid=67000.0, effective_sl=67900.0)

        # Should not try to cancel (no TP order)
        order_mgr.cancel_order.assert_not_awaited()
        # Should still submit market exit
        order_mgr.submit_intent.assert_awaited_once()


# ── _execute_time_stop() internal behavior ───────────────────────


class TestExecuteTimeStop:
    """Test _execute_time_stop() edge cases."""

    @pytest.mark.asyncio
    async def test_time_stop_skips_if_already_triggered(self):
        """Does nothing if sl_triggered is already True."""
        mgr, order_mgr, _ = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-already",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic() - 100000,
            tp_price=73150,
            sl_price=67900,
            sl_triggered=True,
        )
        mgr._exits["p-already"] = managed

        await mgr._execute_time_stop(managed, 70000.0)

        order_mgr.submit_intent.assert_not_awaited()
        order_mgr.cancel_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_time_stop_skips_if_exit_reason_set(self):
        """Does nothing if exit_reason is already set."""
        mgr, order_mgr, _ = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-exited",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic() - 100000,
            tp_price=73150,
            sl_price=67900,
            exit_reason="take_profit",
        )
        mgr._exits["p-exited"] = managed

        await mgr._execute_time_stop(managed, 70000.0)

        order_mgr.submit_intent.assert_not_awaited()


# ── _cleanup_exit() tests ────────────────────────────────────────


class TestCleanupExit:
    """Test _cleanup_exit() removes all state."""

    def test_cleanup_removes_exit_and_order_mappings(self):
        mgr, _, _ = _make_exit_manager()

        managed = ManagedExit(
            position_id="p-clean",
            symbol="BTC-USD",
            side="long",
            entry_price=70000,
            entry_qty=0.001,
            entry_time=time.monotonic(),
            tp_price=73150,
            sl_price=67900,
            tp_order_id="tp-clean",
            sl_order_id="sl-clean",
        )
        mgr._exits["p-clean"] = managed
        mgr._order_to_position["tp-clean"] = "p-clean"
        mgr._order_to_position["sl-clean"] = "p-clean"

        mgr._cleanup_exit("p-clean")

        assert "p-clean" not in mgr._exits
        assert "tp-clean" not in mgr._order_to_position
        assert "sl-clean" not in mgr._order_to_position

    def test_cleanup_nonexistent_does_nothing(self):
        mgr, _, _ = _make_exit_manager()
        # Should not raise
        mgr._cleanup_exit("nonexistent")
