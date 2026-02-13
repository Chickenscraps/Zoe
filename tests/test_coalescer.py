"""Tests for the market data coalescer."""
import asyncio
import pytest
from services.market_data_ws.coalescer import Coalescer, TickerSnapshot


class TestTickerSnapshot:
    """Test TickerSnapshot dataclass."""

    def test_default_values(self):
        snap = TickerSnapshot(symbol="BTC-USD")
        assert snap.bid == 0.0
        assert snap.ask == 0.0
        assert snap.mid == 0.0
        assert snap.spread_pct == 0.0
        assert snap.volume_24h == 0.0
        assert snap.change_24h_pct == 0.0

    def test_custom_values(self):
        snap = TickerSnapshot(symbol="BTC-USD", bid=100.0, ask=102.0)
        assert snap.bid == 100.0
        assert snap.ask == 102.0
        assert snap.symbol == "BTC-USD"


class TestCoalescer:
    """Test coalescer buffer and flush logic."""

    def test_update_stores_latest(self):
        """Only the latest value per symbol should be kept."""
        async def noop(s):
            pass

        c = Coalescer(flush_interval_ms=10_000, on_flush=noop, name="test")

        c.update("BTC-USD", bid=100, ask=101, volume_24h=1000)
        c.update("BTC-USD", bid=200, ask=201, volume_24h=2000)

        # Should only have latest
        latest = c.get_all()
        assert "BTC-USD" in latest
        assert latest["BTC-USD"].bid == 200
        assert latest["BTC-USD"].ask == 201

    def test_multiple_symbols(self):
        async def noop(s):
            pass

        c = Coalescer(flush_interval_ms=10_000, on_flush=noop, name="test")
        c.update("BTC-USD", bid=100, ask=101)
        c.update("ETH-USD", bid=50, ask=51)

        all_snaps = c.get_all()
        assert len(all_snaps) == 2
        assert "BTC-USD" in all_snaps
        assert "ETH-USD" in all_snaps

    def test_dirty_tracking(self):
        """Only dirty symbols should be flushed."""
        async def noop(s):
            pass

        c = Coalescer(flush_interval_ms=10_000, on_flush=noop, name="test")

        c.update("BTC-USD", bid=100, ask=101)
        c.update("ETH-USD", bid=50, ask=51)

        assert len(c._dirty) == 2

        # Clear dirty set (simulating flush)
        c._dirty.clear()
        assert len(c._dirty) == 0

    def test_stats_tracking(self):
        async def noop(s):
            pass

        c = Coalescer(flush_interval_ms=10_000, on_flush=noop, name="test")
        c.update("BTC-USD", bid=100, ask=101)
        c.update("BTC-USD", bid=200, ask=201)
        c.update("ETH-USD", bid=50, ask=51)

        stats = c.stats
        assert isinstance(stats, dict)
        assert stats["total_updates"] == 3
        assert stats["buffered_symbols"] == 2

    def test_mid_and_spread_computed(self):
        """Mid and spread should be auto-computed on update."""
        async def noop(s):
            pass

        c = Coalescer(flush_interval_ms=10_000, on_flush=noop, name="test")
        c.update("BTC-USD", bid=100, ask=102)

        snap = c.get("BTC-USD")
        assert snap is not None
        assert snap.mid == pytest.approx(101.0)
        assert snap.spread_pct == pytest.approx(2.0 / 101.0 * 100)

    def test_get_nonexistent_symbol(self):
        async def noop(s):
            pass

        c = Coalescer(flush_interval_ms=10_000, on_flush=noop, name="test")
        assert c.get("DOES-NOT-EXIST") is None
