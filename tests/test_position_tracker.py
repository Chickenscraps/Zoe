"""Tests for PositionTracker — in-memory + SQLite position state machine."""
import time
import uuid

import pytest
from unittest.mock import MagicMock, patch

from services.crypto_trader.position_tracker import (
    Position,
    PositionStatus,
    PositionTracker,
)


# ── Helpers ──────────────────────────────────────────────────────


def _make_position(
    id: str | None = None,
    symbol: str = "BTC-USD",
    side: str = "long",
    entry_price: float = 69000.0,
    entry_qty: float = 0.001,
    entry_time: float | None = None,
    entry_time_utc: str = "2025-01-15T12:00:00+00:00",
    tp_price: float = 72000.0,
    sl_price: float = 67000.0,
    status: PositionStatus = PositionStatus.OPEN,
    **kwargs,
) -> Position:
    """Create a Position with sensible defaults for testing."""
    return Position(
        id=id or str(uuid.uuid4()),
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        entry_qty=entry_qty,
        entry_time=entry_time if entry_time is not None else time.monotonic(),
        entry_time_utc=entry_time_utc,
        tp_price=tp_price,
        sl_price=sl_price,
        status=status,
        **kwargs,
    )


def _mock_store():
    """Create a mock LocalEventStore with the expected interface."""
    store = MagicMock()
    store.insert_position = MagicMock()
    store.get_open_positions = MagicMock(return_value=[])
    return store


def _mock_price_cache(prices: dict[str, float] | None = None):
    """Create a mock PriceCache that returns {"mid": price} for each symbol."""
    cache = MagicMock()
    prices = prices or {}

    def _snapshot(symbol):
        if symbol in prices:
            return {"mid": prices[symbol]}
        return {"mid": 0.0}

    cache.snapshot = MagicMock(side_effect=_snapshot)
    return cache


def _make_tracker(store=None, mode="paper") -> PositionTracker:
    """Create a PositionTracker with an optional mock store."""
    return PositionTracker(local_store=store, mode=mode)


# ── PositionStatus enum ─────────────────────────────────────────


def test_position_status_values():
    assert PositionStatus.OPEN.value == "open"
    assert PositionStatus.EXIT_PENDING.value == "exit_pending"
    assert PositionStatus.CLOSING.value == "closing"
    assert PositionStatus.CLOSED.value == "closed"


def test_position_status_from_string():
    assert PositionStatus("open") == PositionStatus.OPEN
    assert PositionStatus("exit_pending") == PositionStatus.EXIT_PENDING
    assert PositionStatus("closing") == PositionStatus.CLOSING
    assert PositionStatus("closed") == PositionStatus.CLOSED


def test_position_status_invalid_raises():
    with pytest.raises(ValueError):
        PositionStatus("nonexistent")


# ── Position dataclass properties ────────────────────────────────


def test_position_notional():
    pos = _make_position(entry_price=69000.0, entry_qty=0.001)
    assert pos.notional == pytest.approx(69.0)


def test_position_notional_large_qty():
    pos = _make_position(entry_price=50000.0, entry_qty=2.5)
    assert pos.notional == pytest.approx(125000.0)


def test_is_open_when_open():
    pos = _make_position(status=PositionStatus.OPEN)
    assert pos.is_open is True


def test_is_open_when_exit_pending():
    pos = _make_position(status=PositionStatus.EXIT_PENDING)
    assert pos.is_open is True


def test_is_open_when_closing():
    pos = _make_position(status=PositionStatus.CLOSING)
    assert pos.is_open is True


def test_is_open_when_closed():
    pos = _make_position(status=PositionStatus.CLOSED)
    assert pos.is_open is False


def test_age_seconds_is_positive():
    pos = _make_position(entry_time=time.monotonic() - 10.0)
    assert pos.age_seconds >= 10.0


def test_age_hours_conversion():
    pos = _make_position(entry_time=time.monotonic() - 7200.0)
    assert pos.age_hours == pytest.approx(2.0, abs=0.05)


def test_to_dict_basic_fields():
    pos = _make_position(
        id="test-id-123",
        symbol="ETH-USD",
        side="long",
        entry_price=3500.0,
        entry_qty=1.0,
        entry_time_utc="2025-01-15T12:00:00+00:00",
        tp_price=4000.0,
        sl_price=3200.0,
        mode="paper",
    )
    d = pos.to_dict()
    assert d["id"] == "test-id-123"
    assert d["symbol"] == "ETH-USD"
    assert d["side"] == "long"
    assert d["entry_price"] == 3500.0
    assert d["entry_qty"] == 1.0
    assert d["entry_time_utc"] == "2025-01-15T12:00:00+00:00"
    assert d["tp_price"] == 4000.0
    assert d["sl_price"] == 3200.0
    assert d["mode"] == "paper"


def test_to_dict_status_is_string():
    pos = _make_position(status=PositionStatus.EXIT_PENDING)
    d = pos.to_dict()
    assert d["status"] == "exit_pending"


def test_to_dict_unrealized_pnl_rounded():
    pos = _make_position()
    pos.unrealized_pnl = 1.23456789
    d = pos.to_dict()
    assert d["unrealized_pnl"] == 1.2346


def test_to_dict_realized_pnl_none():
    pos = _make_position()
    d = pos.to_dict()
    assert d["realized_pnl"] is None


def test_to_dict_realized_pnl_rounded():
    pos = _make_position()
    pos.realized_pnl = -5.678901
    d = pos.to_dict()
    assert d["realized_pnl"] == -5.6789


def test_to_dict_optional_fields_none_by_default():
    pos = _make_position()
    d = pos.to_dict()
    assert d["exit_order_id"] is None
    assert d["exit_price"] is None
    assert d["exit_qty"] is None
    assert d["trailing_sl"] is None


def test_to_dict_includes_strategy_and_signal():
    pos = _make_position(strategy="scanner", signal_score=78.5)
    d = pos.to_dict()
    assert d["strategy"] == "scanner"
    assert d["signal_score"] == 78.5


# ── PositionTracker.open_position() ──────────────────────────────


def test_open_position_creates_with_correct_fields():
    store = _mock_store()
    tracker = _make_tracker(store=store, mode="paper")

    pos = tracker.open_position(
        symbol="BTC-USD",
        side="long",
        qty=0.001,
        avg_price=69000.0,
        tp_price=72000.0,
        sl_price=67000.0,
        entry_order_id="O-ENTRY-1",
        strategy="scanner",
        signal_score=85.0,
    )

    assert pos.symbol == "BTC-USD"
    assert pos.side == "long"
    assert pos.entry_price == 69000.0
    assert pos.entry_qty == 0.001
    assert pos.tp_price == 72000.0
    assert pos.sl_price == 67000.0
    assert pos.entry_order_id == "O-ENTRY-1"
    assert pos.strategy == "scanner"
    assert pos.signal_score == 85.0
    assert pos.mode == "paper"
    assert pos.status == PositionStatus.OPEN
    assert pos.high_water_mark == 69000.0


def test_open_position_assigns_unique_id():
    tracker = _make_tracker()
    pos1 = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    pos2 = tracker.open_position("ETH-USD", "long", 1.0, 3500, tp_price=4000, sl_price=3200)
    assert pos1.id != pos2.id
    # IDs should be valid UUIDs
    uuid.UUID(pos1.id)
    uuid.UUID(pos2.id)


def test_open_position_persists_to_store():
    store = _mock_store()
    tracker = _make_tracker(store=store)

    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    store.insert_position.assert_called_once()
    call_data = store.insert_position.call_args[0][0]
    assert call_data["position_id"] == pos.id
    assert call_data["symbol"] == "BTC-USD"
    assert call_data["side"] == "long"
    assert call_data["entry_price"] == 69000.0
    assert call_data["qty"] == 0.001
    assert call_data["status"] == "open"


def test_open_position_logs(caplog):
    tracker = _make_tracker()
    with caplog.at_level("INFO", logger="services.crypto_trader.position_tracker"):
        tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    assert "Position opened" in caplog.text
    assert "BTC-USD" in caplog.text


def test_open_position_uses_provided_entry_time_utc():
    tracker = _make_tracker()
    pos = tracker.open_position(
        "BTC-USD", "long", 0.001, 69000,
        tp_price=72000, sl_price=67000,
        entry_time_utc="2025-06-01T00:00:00Z",
    )
    assert pos.entry_time_utc == "2025-06-01T00:00:00Z"


def test_open_position_generates_entry_time_utc_if_not_provided():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    # Should be an ISO format string
    assert "T" in pos.entry_time_utc


# ── PositionTracker.begin_exit() ─────────────────────────────────


def test_begin_exit_changes_status():
    store = _mock_store()
    tracker = _make_tracker(store=store)
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    tracker.begin_exit(pos.id, exit_order_id="O-EXIT-1")

    assert pos.status == PositionStatus.EXIT_PENDING
    assert pos.exit_order_id == "O-EXIT-1"


def test_begin_exit_persists():
    store = _mock_store()
    tracker = _make_tracker(store=store)
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    store.insert_position.reset_mock()

    tracker.begin_exit(pos.id, exit_order_id="O-EXIT-1")

    store.insert_position.assert_called_once()
    call_data = store.insert_position.call_args[0][0]
    assert call_data["status"] == "exit_pending"
    assert call_data["exit_order_id"] == "O-EXIT-1"


def test_begin_exit_no_op_for_unknown_position(caplog):
    tracker = _make_tracker()
    with caplog.at_level("WARNING", logger="services.crypto_trader.position_tracker"):
        tracker.begin_exit("nonexistent-id", exit_order_id="O-EXIT-1")
    assert "unknown position" in caplog.text


def test_begin_exit_no_op_for_closed_position():
    store = _mock_store()
    tracker = _make_tracker(store=store)
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.close_position(pos.id, exit_price=72000.0)
    store.insert_position.reset_mock()

    tracker.begin_exit(pos.id, exit_order_id="O-EXIT-2")

    assert pos.status == PositionStatus.CLOSED
    store.insert_position.assert_not_called()


# ── PositionTracker.mark_closing() ───────────────────────────────


def test_mark_closing_changes_status():
    store = _mock_store()
    tracker = _make_tracker(store=store)
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    tracker.mark_closing(pos.id)

    assert pos.status == PositionStatus.CLOSING


def test_mark_closing_persists():
    store = _mock_store()
    tracker = _make_tracker(store=store)
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    store.insert_position.reset_mock()

    tracker.mark_closing(pos.id)

    store.insert_position.assert_called_once()
    call_data = store.insert_position.call_args[0][0]
    assert call_data["status"] == "closing"


def test_mark_closing_no_op_for_unknown():
    store = _mock_store()
    tracker = _make_tracker(store=store)
    store.insert_position.reset_mock()

    tracker.mark_closing("nonexistent-id")

    store.insert_position.assert_not_called()


def test_mark_closing_no_op_for_closed():
    store = _mock_store()
    tracker = _make_tracker(store=store)
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.close_position(pos.id, exit_price=72000.0)
    store.insert_position.reset_mock()

    tracker.mark_closing(pos.id)

    assert pos.status == PositionStatus.CLOSED
    store.insert_position.assert_not_called()


# ── PositionTracker.close_position() ─────────────────────────────


def test_close_position_changes_status():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    result = tracker.close_position(pos.id, exit_price=72000.0)

    assert result is not None
    assert result.status == PositionStatus.CLOSED


def test_close_position_sets_exit_fields():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    result = tracker.close_position(pos.id, exit_price=72000.0, exit_qty=0.001)

    assert result.exit_price == 72000.0
    assert result.exit_qty == 0.001
    assert result.exit_time is not None


def test_close_position_defaults_exit_qty_to_entry_qty():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    result = tracker.close_position(pos.id, exit_price=72000.0)

    assert result.exit_qty == 0.001


def test_close_position_computes_pnl_long():
    """Long PnL = (exit_price - entry_price) * qty."""
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    result = tracker.close_position(pos.id, exit_price=72000.0)

    expected_pnl = (72000.0 - 69000.0) * 0.001  # 3.0
    assert result.realized_pnl == pytest.approx(expected_pnl)


def test_close_position_computes_pnl_long_loss():
    """Long PnL is negative when exit < entry."""
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    result = tracker.close_position(pos.id, exit_price=67000.0)

    expected_pnl = (67000.0 - 69000.0) * 0.001  # -2.0
    assert result.realized_pnl == pytest.approx(expected_pnl)


def test_close_position_computes_pnl_short():
    """Short PnL = (entry_price - exit_price) * qty."""
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "short", 0.001, 69000, tp_price=66000, sl_price=71000)

    result = tracker.close_position(pos.id, exit_price=66000.0)

    expected_pnl = (69000.0 - 66000.0) * 0.001  # 3.0
    assert result.realized_pnl == pytest.approx(expected_pnl)


def test_close_position_computes_pnl_short_loss():
    """Short PnL is negative when exit > entry."""
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "short", 0.001, 69000, tp_price=66000, sl_price=71000)

    result = tracker.close_position(pos.id, exit_price=71000.0)

    expected_pnl = (69000.0 - 71000.0) * 0.001  # -2.0
    assert result.realized_pnl == pytest.approx(expected_pnl)


def test_close_position_uses_provided_pnl():
    """If realized_pnl is given explicitly, use it instead of computing."""
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    result = tracker.close_position(pos.id, exit_price=72000.0, realized_pnl=2.85)

    assert result.realized_pnl == 2.85


def test_close_position_zeroes_unrealized_pnl():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    pos.unrealized_pnl = 1.5

    result = tracker.close_position(pos.id, exit_price=72000.0)

    assert result.unrealized_pnl == 0.0


def test_close_position_persists():
    store = _mock_store()
    tracker = _make_tracker(store=store)
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    store.insert_position.reset_mock()

    tracker.close_position(pos.id, exit_price=72000.0)

    store.insert_position.assert_called_once()
    call_data = store.insert_position.call_args[0][0]
    assert call_data["status"] == "closed"
    assert call_data["exit_price"] == 72000.0


def test_close_position_unknown_returns_none(caplog):
    tracker = _make_tracker()
    with caplog.at_level("WARNING", logger="services.crypto_trader.position_tracker"):
        result = tracker.close_position("nonexistent-id", exit_price=72000.0)
    assert result is None
    assert "unknown position" in caplog.text


def test_close_position_logs(caplog):
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    with caplog.at_level("INFO", logger="services.crypto_trader.position_tracker"):
        tracker.close_position(pos.id, exit_price=72000.0)
    assert "Position closed" in caplog.text


# ── PositionTracker.update_marks() ───────────────────────────────


def test_update_marks_long_unrealized_pnl():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    cache = _mock_price_cache({"BTC-USD": 70000.0})

    tracker.update_marks(cache)

    expected = (70000.0 - 69000.0) * 0.001  # 1.0
    assert pos.unrealized_pnl == pytest.approx(expected)


def test_update_marks_short_unrealized_pnl():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "short", 0.001, 69000, tp_price=66000, sl_price=71000)
    cache = _mock_price_cache({"BTC-USD": 68000.0})

    tracker.update_marks(cache)

    expected = (69000.0 - 68000.0) * 0.001  # 1.0
    assert pos.unrealized_pnl == pytest.approx(expected)


def test_update_marks_long_negative_pnl():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    cache = _mock_price_cache({"BTC-USD": 68000.0})

    tracker.update_marks(cache)

    expected = (68000.0 - 69000.0) * 0.001  # -1.0
    assert pos.unrealized_pnl == pytest.approx(expected)


def test_update_marks_updates_high_water_mark_long():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    assert pos.high_water_mark == 69000.0

    cache = _mock_price_cache({"BTC-USD": 71000.0})
    tracker.update_marks(cache)
    assert pos.high_water_mark == 71000.0

    # Price drops but HWM stays at peak
    cache2 = _mock_price_cache({"BTC-USD": 70000.0})
    tracker.update_marks(cache2)
    assert pos.high_water_mark == 71000.0


def test_update_marks_updates_high_water_mark_short():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "short", 0.001, 69000, tp_price=66000, sl_price=71000)

    cache = _mock_price_cache({"BTC-USD": 67000.0})
    tracker.update_marks(cache)
    # For short, HWM tracks lowest price (best for short)
    assert pos.high_water_mark == 67000.0

    # Price rises but HWM stays at trough
    cache2 = _mock_price_cache({"BTC-USD": 68000.0})
    tracker.update_marks(cache2)
    assert pos.high_water_mark == 67000.0


def test_update_marks_skips_closed_positions():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.close_position(pos.id, exit_price=72000.0)

    cache = _mock_price_cache({"BTC-USD": 75000.0})
    tracker.update_marks(cache)

    # Closed position should not be updated
    assert pos.unrealized_pnl == 0.0


def test_update_marks_handles_missing_price():
    """Symbol not in price cache returns mid=0 and is skipped."""
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    cache = _mock_price_cache({})  # No prices at all

    tracker.update_marks(cache)

    # pnl should remain at default 0
    assert pos.unrealized_pnl == 0.0


def test_update_marks_handles_zero_mid():
    """mid=0 should be skipped."""
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    cache = _mock_price_cache({"BTC-USD": 0.0})

    tracker.update_marks(cache)

    assert pos.unrealized_pnl == 0.0


def test_update_marks_handles_negative_mid():
    """Negative mid price should be skipped."""
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    cache = _mock_price_cache({"BTC-USD": -1.0})

    tracker.update_marks(cache)

    assert pos.unrealized_pnl == 0.0


def test_update_marks_multiple_positions():
    tracker = _make_tracker()
    pos1 = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    pos2 = tracker.open_position("ETH-USD", "long", 1.0, 3500, tp_price=4000, sl_price=3200)
    cache = _mock_price_cache({"BTC-USD": 70000.0, "ETH-USD": 3600.0})

    tracker.update_marks(cache)

    assert pos1.unrealized_pnl == pytest.approx(1.0)   # (70000-69000)*0.001
    assert pos2.unrealized_pnl == pytest.approx(100.0)  # (3600-3500)*1.0


# ── PositionTracker.get_open() ───────────────────────────────────


def test_get_open_returns_non_closed():
    tracker = _make_tracker()
    pos1 = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    pos2 = tracker.open_position("ETH-USD", "long", 1.0, 3500, tp_price=4000, sl_price=3200)
    tracker.close_position(pos2.id, exit_price=4000.0)

    open_positions = tracker.get_open()
    assert len(open_positions) == 1
    assert open_positions[0].id == pos1.id


def test_get_open_includes_exit_pending_and_closing():
    tracker = _make_tracker()
    pos1 = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    pos2 = tracker.open_position("ETH-USD", "long", 1.0, 3500, tp_price=4000, sl_price=3200)
    tracker.begin_exit(pos1.id, exit_order_id="O-1")
    tracker.mark_closing(pos2.id)

    open_positions = tracker.get_open()
    assert len(open_positions) == 2


def test_get_open_empty():
    tracker = _make_tracker()
    assert tracker.get_open() == []


# ── PositionTracker.get_all() ────────────────────────────────────


def test_get_all_returns_everything():
    tracker = _make_tracker()
    pos1 = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    pos2 = tracker.open_position("ETH-USD", "long", 1.0, 3500, tp_price=4000, sl_price=3200)
    tracker.close_position(pos2.id, exit_price=4000.0)

    all_positions = tracker.get_all()
    assert len(all_positions) == 2


def test_get_all_empty():
    tracker = _make_tracker()
    assert tracker.get_all() == []


# ── PositionTracker.get_exposure() ───────────────────────────────


def test_get_exposure_per_symbol():
    tracker = _make_tracker()
    tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.open_position("ETH-USD", "long", 1.0, 3500, tp_price=4000, sl_price=3200)

    exposure = tracker.get_exposure()
    assert exposure["BTC-USD"] == pytest.approx(69.0)
    assert exposure["ETH-USD"] == pytest.approx(3500.0)


def test_get_exposure_excludes_closed():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.close_position(pos.id, exit_price=72000.0)

    exposure = tracker.get_exposure()
    assert "BTC-USD" not in exposure


def test_get_exposure_aggregates_same_symbol():
    tracker = _make_tracker()
    tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.open_position("BTC-USD", "long", 0.002, 70000, tp_price=73000, sl_price=68000)

    exposure = tracker.get_exposure()
    expected = (69000 * 0.001) + (70000 * 0.002)  # 69 + 140 = 209
    assert exposure["BTC-USD"] == pytest.approx(expected)


def test_get_exposure_empty():
    tracker = _make_tracker()
    assert tracker.get_exposure() == {}


# ── PositionTracker.get_total_exposure() ─────────────────────────


def test_get_total_exposure():
    tracker = _make_tracker()
    tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.open_position("ETH-USD", "long", 1.0, 3500, tp_price=4000, sl_price=3200)

    total = tracker.get_total_exposure()
    assert total == pytest.approx(69.0 + 3500.0)


def test_get_total_exposure_empty():
    tracker = _make_tracker()
    assert tracker.get_total_exposure() == 0.0


def test_get_total_exposure_excludes_closed():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.open_position("ETH-USD", "long", 1.0, 3500, tp_price=4000, sl_price=3200)
    tracker.close_position(pos.id, exit_price=72000.0)

    total = tracker.get_total_exposure()
    assert total == pytest.approx(3500.0)


# ── PositionTracker.has_position() ───────────────────────────────


def test_has_position_true_when_open():
    tracker = _make_tracker()
    tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    assert tracker.has_position("BTC-USD") is True


def test_has_position_false_when_closed():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.close_position(pos.id, exit_price=72000.0)
    assert tracker.has_position("BTC-USD") is False


def test_has_position_false_when_never_opened():
    tracker = _make_tracker()
    assert tracker.has_position("DOGE-USD") is False


def test_has_position_true_when_exit_pending():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.begin_exit(pos.id, exit_order_id="O-1")
    assert tracker.has_position("BTC-USD") is True


# ── PositionTracker.get_position_by_symbol() ─────────────────────


def test_get_position_by_symbol_found():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    result = tracker.get_position_by_symbol("BTC-USD")
    assert result is not None
    assert result.id == pos.id


def test_get_position_by_symbol_not_found():
    tracker = _make_tracker()
    assert tracker.get_position_by_symbol("DOGE-USD") is None


def test_get_position_by_symbol_skips_closed():
    tracker = _make_tracker()
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    tracker.close_position(pos.id, exit_price=72000.0)

    assert tracker.get_position_by_symbol("BTC-USD") is None


def test_get_position_by_symbol_returns_first_open():
    tracker = _make_tracker()
    pos1 = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    _pos2 = tracker.open_position("BTC-USD", "long", 0.002, 70000, tp_price=73000, sl_price=68000)

    result = tracker.get_position_by_symbol("BTC-USD")
    # Should return one of the two open BTC-USD positions
    assert result is not None
    assert result.symbol == "BTC-USD"
    assert result.is_open is True


# ── PositionTracker.position_count() ─────────────────────────────


def test_position_count_open_only():
    tracker = _make_tracker()
    tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    pos2 = tracker.open_position("ETH-USD", "long", 1.0, 3500, tp_price=4000, sl_price=3200)
    tracker.close_position(pos2.id, exit_price=4000.0)

    assert tracker.position_count() == 1


def test_position_count_empty():
    tracker = _make_tracker()
    assert tracker.position_count() == 0


def test_position_count_includes_exit_pending_and_closing():
    tracker = _make_tracker()
    pos1 = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    pos2 = tracker.open_position("ETH-USD", "long", 1.0, 3500, tp_price=4000, sl_price=3200)
    pos3 = tracker.open_position("SOL-USD", "long", 10.0, 150, tp_price=180, sl_price=130)
    tracker.begin_exit(pos1.id, exit_order_id="O-1")
    tracker.mark_closing(pos2.id)

    assert tracker.position_count() == 3


# ── PositionTracker.recover() ────────────────────────────────────


def test_recover_restores_positions():
    store = _mock_store()
    store.get_open_positions.return_value = [
        {
            "position_id": "recovered-1",
            "symbol": "BTC-USD",
            "side": "long",
            "entry_price": 69000,
            "qty": 0.001,
            "entry_time": "2025-01-15T12:00:00+00:00",
            "tp_price": 72000,
            "sl_price": 67000,
            "status": "open",
            "exit_order_id": None,
            "entry_order_id": "O-ENTRY-1",
            "strategy": "scanner",
        },
        {
            "position_id": "recovered-2",
            "symbol": "ETH-USD",
            "side": "short",
            "entry_price": 3500,
            "qty": 1.0,
            "entry_time": "2025-01-15T13:00:00+00:00",
            "tp_price": 3200,
            "sl_price": 3800,
            "status": "exit_pending",
            "exit_order_id": "O-EXIT-99",
            "entry_order_id": None,
            "strategy": None,
        },
    ]
    tracker = _make_tracker(store=store, mode="paper")

    count = tracker.recover()

    assert count == 2
    assert len(tracker.get_open()) == 2
    assert tracker.has_position("BTC-USD")
    assert tracker.has_position("ETH-USD")

    btc = tracker.get_position_by_symbol("BTC-USD")
    assert btc.id == "recovered-1"
    assert btc.side == "long"
    assert btc.entry_price == 69000.0
    assert btc.status == PositionStatus.OPEN

    eth = tracker.get_position_by_symbol("ETH-USD")
    assert eth.id == "recovered-2"
    assert eth.status == PositionStatus.EXIT_PENDING
    assert eth.exit_order_id == "O-EXIT-99"


def test_recover_skips_closed_positions():
    store = _mock_store()
    store.get_open_positions.return_value = [
        {
            "position_id": "closed-1",
            "symbol": "BTC-USD",
            "side": "long",
            "entry_price": 69000,
            "qty": 0.001,
            "entry_time": "2025-01-15T12:00:00+00:00",
            "tp_price": 72000,
            "sl_price": 67000,
            "status": "closed",
        },
        {
            "position_id": "open-1",
            "symbol": "ETH-USD",
            "side": "long",
            "entry_price": 3500,
            "qty": 1.0,
            "entry_time": "2025-01-15T13:00:00+00:00",
            "tp_price": 4000,
            "sl_price": 3200,
            "status": "open",
        },
    ]
    tracker = _make_tracker(store=store)

    count = tracker.recover()

    assert count == 1
    assert tracker.has_position("ETH-USD")
    assert not tracker.has_position("BTC-USD")


def test_recover_handles_empty_result():
    store = _mock_store()
    store.get_open_positions.return_value = []
    tracker = _make_tracker(store=store)

    count = tracker.recover()

    assert count == 0
    assert tracker.get_all() == []


def test_recover_handles_store_error(caplog):
    store = _mock_store()
    store.get_open_positions.side_effect = Exception("DB connection lost")
    tracker = _make_tracker(store=store)

    with caplog.at_level("ERROR", logger="services.crypto_trader.position_tracker"):
        count = tracker.recover()

    assert count == 0
    assert "Position recovery failed" in caplog.text


def test_recover_no_store_returns_zero():
    tracker = _make_tracker(store=None)
    count = tracker.recover()
    assert count == 0


def test_recover_with_override_store():
    """recover() accepts a local_store parameter to override the instance store."""
    override_store = _mock_store()
    override_store.get_open_positions.return_value = [
        {
            "position_id": "override-1",
            "symbol": "SOL-USD",
            "side": "long",
            "entry_price": 150,
            "qty": 10.0,
            "entry_time": "2025-01-15T14:00:00+00:00",
            "tp_price": 180,
            "sl_price": 130,
            "status": "open",
        },
    ]
    tracker = _make_tracker(store=None)  # No instance store

    count = tracker.recover(local_store=override_store)

    assert count == 1
    assert tracker.has_position("SOL-USD")


def test_recover_handles_invalid_status_string():
    """Unknown status strings fall back to OPEN."""
    store = _mock_store()
    store.get_open_positions.return_value = [
        {
            "position_id": "weird-1",
            "symbol": "BTC-USD",
            "side": "long",
            "entry_price": 69000,
            "qty": 0.001,
            "entry_time": "2025-01-15T12:00:00+00:00",
            "tp_price": 72000,
            "sl_price": 67000,
            "status": "invalid_status_value",
        },
    ]
    tracker = _make_tracker(store=store)

    count = tracker.recover()

    assert count == 1
    pos = tracker.get_position_by_symbol("BTC-USD")
    assert pos.status == PositionStatus.OPEN


def test_recover_handles_missing_status():
    """Missing status key defaults to 'open'."""
    store = _mock_store()
    store.get_open_positions.return_value = [
        {
            "position_id": "no-status",
            "symbol": "BTC-USD",
            "side": "long",
            "entry_price": 69000,
            "qty": 0.001,
            "entry_time": "2025-01-15T12:00:00+00:00",
            "tp_price": 72000,
            "sl_price": 67000,
            # "status" key missing
        },
    ]
    tracker = _make_tracker(store=store)

    count = tracker.recover()

    assert count == 1
    pos = tracker.get_position_by_symbol("BTC-USD")
    assert pos.status == PositionStatus.OPEN


def test_recover_uses_correct_mode():
    store = _mock_store()
    store.get_open_positions.return_value = []
    tracker = _make_tracker(store=store, mode="live")

    tracker.recover()

    store.get_open_positions.assert_called_once_with("live")


# ── PositionTracker._persist() ───────────────────────────────────


def test_persist_calls_store_with_correct_data():
    store = _mock_store()
    tracker = _make_tracker(store=store, mode="paper")
    pos = tracker.open_position(
        "BTC-USD", "long", 0.001, 69000,
        tp_price=72000, sl_price=67000,
        entry_order_id="O-ENTRY-1",
        strategy="scanner",
        signal_score=85.0,
    )

    # open_position already calls _persist, check the call
    store.insert_position.assert_called_once()
    data = store.insert_position.call_args[0][0]

    assert data["position_id"] == pos.id
    assert data["symbol"] == "BTC-USD"
    assert data["side"] == "long"
    assert data["entry_price"] == 69000.0
    assert data["size_usd"] == pytest.approx(69.0)
    assert data["qty"] == 0.001
    assert data["tp_price"] == 72000.0
    assert data["sl_price"] == 67000.0
    assert data["exit_price"] is None
    assert data["exit_time"] is None
    assert data["pnl_usd"] is None
    assert data["status"] == "open"
    assert data["entry_order_id"] == "O-ENTRY-1"
    assert data["exit_order_id"] is None
    assert data["signal_strength"] == 85.0
    assert data["regime"] is None
    assert data["mode"] == "paper"


def test_persist_handles_no_store():
    """Tracker with no store should not raise on persist."""
    tracker = _make_tracker(store=None)
    # open_position internally calls _persist, should not raise
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    assert pos is not None


def test_persist_handles_store_error(caplog):
    store = _mock_store()
    store.insert_position.side_effect = Exception("Write failed")
    tracker = _make_tracker(store=store)

    with caplog.at_level("ERROR", logger="services.crypto_trader.position_tracker"):
        # open_position calls _persist which should catch the exception
        pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)

    assert pos is not None  # Position is still created in memory
    assert "Position persist failed" in caplog.text


def test_persist_on_close_includes_exit_data():
    store = _mock_store()
    tracker = _make_tracker(store=store)
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    store.insert_position.reset_mock()

    tracker.close_position(pos.id, exit_price=72000.0, realized_pnl=3.0)

    data = store.insert_position.call_args[0][0]
    assert data["status"] == "closed"
    assert data["exit_price"] == 72000.0
    assert data["pnl_usd"] == 3.0
    assert data["exit_time"] is not None


# ── Full lifecycle integration ───────────────────────────────────


def test_full_lifecycle_open_to_close():
    """Walk through the full state machine: OPEN -> EXIT_PENDING -> CLOSING -> CLOSED."""
    store = _mock_store()
    tracker = _make_tracker(store=store, mode="paper")

    # 1. Open
    pos = tracker.open_position("BTC-USD", "long", 0.001, 69000, tp_price=72000, sl_price=67000)
    assert pos.status == PositionStatus.OPEN
    assert tracker.position_count() == 1

    # 2. Update marks
    cache = _mock_price_cache({"BTC-USD": 70500.0})
    tracker.update_marks(cache)
    assert pos.unrealized_pnl == pytest.approx((70500 - 69000) * 0.001)

    # 3. Begin exit
    tracker.begin_exit(pos.id, exit_order_id="O-EXIT-1")
    assert pos.status == PositionStatus.EXIT_PENDING
    assert tracker.position_count() == 1  # Still open

    # 4. Mark closing
    tracker.mark_closing(pos.id)
    assert pos.status == PositionStatus.CLOSING
    assert tracker.position_count() == 1  # Still open

    # 5. Close
    result = tracker.close_position(pos.id, exit_price=72000.0)
    assert result.status == PositionStatus.CLOSED
    assert result.realized_pnl == pytest.approx(3.0)
    assert result.unrealized_pnl == 0.0
    assert tracker.position_count() == 0
    assert tracker.has_position("BTC-USD") is False

    # Store was called 4 times: open, begin_exit, mark_closing, close
    assert store.insert_position.call_count == 4
