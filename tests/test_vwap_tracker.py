"""Tests for VWAP (Volume-Weighted Average Price) Tracker."""
import pytest
from services.signals.vwap_tracker import VWAPTracker, VWAPState


class TestVWAPTracker:
    """Test VWAP computation and execution benchmarks."""

    def test_empty_returns_none(self):
        """No data should return None."""
        tracker = VWAPTracker()
        assert tracker.get_state("BTC-USD") is None

    def test_single_trade_vwap_equals_price(self):
        """VWAP of a single trade equals the trade price."""
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=97000, volume=1.0)
        state = tracker.get_state("BTC-USD")
        assert state is not None
        assert state.vwap == 97000

    def test_vwap_weighted_by_volume(self):
        """VWAP should be weighted by volume."""
        tracker = VWAPTracker()
        # 1 BTC at $97000, 3 BTC at $97400
        tracker.record_trade("BTC-USD", price=97000, volume=1.0)
        tracker.record_trade("BTC-USD", price=97400, volume=3.0)

        state = tracker.get_state("BTC-USD")
        assert state is not None
        # VWAP = (97000*1 + 97400*3) / (1+3) = (97000 + 292200) / 4 = 97300
        assert state.vwap == 97300

    def test_price_above_vwap(self):
        """Price above VWAP should show positive deviation."""
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=97000, volume=1.0)
        tracker.record_trade("BTC-USD", price=97200, volume=1.0)

        state = tracker.get_state("BTC-USD", current_price=97500)
        assert state is not None
        assert state.is_above_vwap
        assert state.price_vs_vwap_pct > 0

    def test_price_below_vwap(self):
        """Price below VWAP should show negative deviation."""
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=97000, volume=1.0)
        tracker.record_trade("BTC-USD", price=97200, volume=1.0)

        state = tracker.get_state("BTC-USD", current_price=96900)
        assert state is not None
        assert not state.is_above_vwap
        assert state.price_vs_vwap_pct < 0

    def test_should_buy_below_vwap(self):
        """should_buy returns True when price is below VWAP."""
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=97000, volume=1.0)
        tracker.record_trade("BTC-USD", price=97200, volume=1.0)
        # VWAP = 97100
        assert tracker.should_buy("BTC-USD", current_price=96900)
        assert not tracker.should_buy("BTC-USD", current_price=97300)

    def test_should_sell_above_vwap(self):
        """should_sell returns True when price is above VWAP."""
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=97000, volume=1.0)
        tracker.record_trade("BTC-USD", price=97200, volume=1.0)
        # VWAP = 97100
        assert tracker.should_sell("BTC-USD", current_price=97300)
        assert not tracker.should_sell("BTC-USD", current_price=96900)

    def test_deviation_bands(self):
        """Test deviation band classification."""
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=100000, volume=1.0)

        # At VWAP
        state = tracker.get_state("BTC-USD", current_price=100000)
        assert state.deviation_band == "at_vwap"

        # Near VWAP (0.2%)
        state = tracker.get_state("BTC-USD", current_price=100200)
        assert state.deviation_band == "near_vwap"

        # Significant deviation (1.5%)
        state = tracker.get_state("BTC-USD", current_price=101500)
        assert state.deviation_band == "significant_deviation"

    def test_multiple_symbols(self):
        """VWAP tracked independently per symbol."""
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=97000, volume=1.0)
        tracker.record_trade("ETH-USD", price=2700, volume=10.0)

        btc = tracker.get_state("BTC-USD")
        eth = tracker.get_state("ETH-USD")

        assert btc.vwap == 97000
        assert eth.vwap == 2700

    def test_reset_session(self):
        """Reset should clear all data."""
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=97000, volume=1.0)
        assert tracker.get_state("BTC-USD") is not None

        tracker.reset_session("BTC-USD")
        assert tracker.get_state("BTC-USD") is None

    def test_zero_volume_ignored(self):
        """Zero or negative volume trades should be ignored."""
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=97000, volume=0)
        tracker.record_trade("BTC-USD", price=97000, volume=-1)
        assert tracker.get_state("BTC-USD") is None

    def test_zero_price_ignored(self):
        """Zero or negative price trades should be ignored."""
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=0, volume=1.0)
        tracker.record_trade("BTC-USD", price=-100, volume=1.0)
        assert tracker.get_state("BTC-USD") is None
