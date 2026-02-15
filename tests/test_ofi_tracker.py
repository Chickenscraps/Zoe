"""Tests for Order Flow Imbalance (OFI) Tracker."""
import time
import pytest
from services.signals.ofi_tracker import OFITracker, OFISignal


class TestOFITracker:
    """Test OFI signal computation."""

    def test_first_update_returns_none(self):
        """First BBO observation should not produce a signal."""
        tracker = OFITracker()
        result = tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97010, ask_size=1.0)
        assert result is None

    def test_second_update_returns_signal(self):
        """Second BBO observation should produce a signal."""
        tracker = OFITracker()
        tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97010, ask_size=1.0)
        result = tracker.update("BTC-USD", bid=97000, bid_size=1.5, ask=97010, ask_size=1.0)
        assert result is not None
        assert isinstance(result, OFISignal)
        assert result.symbol == "BTC-USD"

    def test_bullish_ofi_bid_size_increase(self):
        """Increasing bid size = demand increase = positive OFI."""
        tracker = OFITracker()
        tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97010, ask_size=1.0)
        result = tracker.update("BTC-USD", bid=97000, bid_size=5.0, ask=97010, ask_size=1.0)
        assert result is not None
        assert result.ofi_1s > 0  # Positive = bullish

    def test_bearish_ofi_ask_size_increase(self):
        """Increasing ask size = supply increase = negative OFI."""
        tracker = OFITracker()
        tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97010, ask_size=1.0)
        result = tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97010, ask_size=5.0)
        assert result is not None
        assert result.ofi_1s < 0  # Negative = bearish

    def test_bid_price_rise_bullish(self):
        """Bid price rising = fresh demand = strong bullish OFI."""
        tracker = OFITracker()
        tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97010, ask_size=1.0)
        result = tracker.update("BTC-USD", bid=97005, bid_size=2.0, ask=97010, ask_size=1.0)
        assert result is not None
        assert result.ofi_1s > 0

    def test_ask_price_drop_bearish(self):
        """Ask price dropping = fresh supply = bearish OFI."""
        tracker = OFITracker()
        tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97010, ask_size=1.0)
        result = tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97005, ask_size=2.0)
        assert result is not None
        assert result.ofi_1s < 0

    def test_multiple_symbols_independent(self):
        """OFI tracked independently per symbol."""
        tracker = OFITracker()
        tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97010, ask_size=1.0)
        tracker.update("ETH-USD", bid=2700, bid_size=10.0, ask=2705, ask_size=10.0)

        btc = tracker.update("BTC-USD", bid=97000, bid_size=3.0, ask=97010, ask_size=1.0)
        eth = tracker.update("ETH-USD", bid=2700, bid_size=10.0, ask=2705, ask_size=20.0)

        assert btc is not None and btc.ofi_1s > 0  # BTC bullish
        assert eth is not None and eth.ofi_1s < 0  # ETH bearish

    def test_get_signal_without_update(self):
        """get_signal returns None if no data exists."""
        tracker = OFITracker()
        assert tracker.get_signal("BTC-USD") is None

    def test_cleanup_removes_stale(self):
        """Cleanup removes old entries."""
        tracker = OFITracker()
        tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97010, ask_size=1.0)
        tracker.update("BTC-USD", bid=97000, bid_size=2.0, ask=97010, ask_size=1.0)

        # Should have data
        assert tracker.get_signal("BTC-USD") is not None

        # Cleanup with 0s max_age removes everything
        removed = tracker.cleanup(max_age_seconds=0)
        assert removed > 0

    def test_neutral_direction_for_small_changes(self):
        """Small OFI changes should be classified as neutral."""
        tracker = OFITracker(strength_threshold=1.0)
        tracker.update("BTC-USD", bid=97000, bid_size=1.0, ask=97010, ask_size=1.0)
        result = tracker.update("BTC-USD", bid=97000, bid_size=1.001, ask=97010, ask_size=1.0)
        assert result is not None
        assert result.direction == "neutral"


class TestOFIDelta:
    """Test the core OFI delta computation."""

    def test_no_change_zero_delta(self):
        """No change in BBO = zero OFI delta."""
        from services.signals.ofi_tracker import BBOState
        prev = BBOState(bid_price=100, bid_size=1.0, ask_price=101, ask_size=1.0)
        delta = OFITracker._compute_ofi_delta(prev, 100, 1.0, 101, 1.0)
        assert delta == 0.0

    def test_symmetric_increase(self):
        """Equal bid/ask size increase = zero net OFI."""
        from services.signals.ofi_tracker import BBOState
        prev = BBOState(bid_price=100, bid_size=1.0, ask_price=101, ask_size=1.0)
        delta = OFITracker._compute_ofi_delta(prev, 100, 2.0, 101, 2.0)
        assert delta == 0.0  # +1 demand, +1 supply = net 0
