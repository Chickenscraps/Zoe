"""Tests for FIFO cost-basis matcher."""
import pytest
from services.accounting.fifo_matcher import FIFOMatcher, Lot


class TestFIFOMatcher:
    """Test FIFO cost-basis matching logic."""

    def test_simple_buy_sell_round_trip(self):
        """Buy 1 BTC at $100, sell 1 BTC at $110 → $10 realized."""
        m = FIFOMatcher()
        m.process_fill("BTC-USD", "buy", 1.0, 100.0, 0.0)
        result = m.process_fill("BTC-USD", "sell", 1.0, 110.0, 0.0)

        assert result is not None
        assert result.realized_pnl == pytest.approx(10.0)
        assert m.get_realized_pnl() == pytest.approx(10.0)
        assert m.get_open_qty("BTC-USD") == pytest.approx(0.0)

    def test_fifo_order(self):
        """Buy at $100, then $200. Sell should match $100 first (FIFO)."""
        m = FIFOMatcher()
        m.process_fill("BTC-USD", "buy", 1.0, 100.0, 0.0)
        m.process_fill("BTC-USD", "buy", 1.0, 200.0, 0.0)

        result = m.process_fill("BTC-USD", "sell", 1.0, 150.0, 0.0)

        assert result is not None
        # Sold at 150, cost was 100 → +50
        assert result.realized_pnl == pytest.approx(50.0)
        # Still have 1 BTC at $200
        assert m.get_open_qty("BTC-USD") == pytest.approx(1.0)
        assert m.get_cost_basis("BTC-USD") == pytest.approx(200.0)

    def test_partial_lot_consumption(self):
        """Buy 2 BTC at $100, sell 1 → partial lot remains."""
        m = FIFOMatcher()
        m.process_fill("BTC-USD", "buy", 2.0, 100.0, 0.0)
        result = m.process_fill("BTC-USD", "sell", 1.0, 120.0, 0.0)

        assert result is not None
        assert result.realized_pnl == pytest.approx(20.0)
        assert m.get_open_qty("BTC-USD") == pytest.approx(1.0)

    def test_fees_reduce_realized_pnl(self):
        """Fees on both buy and sell reduce realized P&L."""
        m = FIFOMatcher()
        m.process_fill("BTC-USD", "buy", 1.0, 100.0, 1.0)  # $1 buy fee
        result = m.process_fill("BTC-USD", "sell", 1.0, 110.0, 1.0)  # $1 sell fee

        assert result is not None
        # Gross: 110 - 100 = 10. Fees: 1 (buy) + 1 (sell) = 2. Net: 8
        assert result.realized_pnl == pytest.approx(8.0)

    def test_multi_symbol(self):
        """Different symbols tracked independently."""
        m = FIFOMatcher()
        m.process_fill("BTC-USD", "buy", 1.0, 100.0, 0.0)
        m.process_fill("ETH-USD", "buy", 10.0, 50.0, 0.0)

        m.process_fill("BTC-USD", "sell", 1.0, 120.0, 0.0)
        m.process_fill("ETH-USD", "sell", 10.0, 45.0, 0.0)

        assert m.get_realized_pnl("BTC-USD") == pytest.approx(20.0)
        assert m.get_realized_pnl("ETH-USD") == pytest.approx(-50.0)
        assert m.get_realized_pnl() == pytest.approx(-30.0)

    def test_unrealized_pnl(self):
        """Unrealized P&L from open lots at mark price."""
        m = FIFOMatcher()
        m.process_fill("BTC-USD", "buy", 1.0, 100.0, 0.0)

        # Mark at $120 → $20 unrealized
        assert m.get_unrealized_pnl("BTC-USD", 120.0) == pytest.approx(20.0)
        # Mark at $80 → -$20 unrealized
        assert m.get_unrealized_pnl("BTC-USD", 80.0) == pytest.approx(-20.0)

    def test_unrealized_pnl_with_fees(self):
        """Unrealized P&L includes buy fees as cost."""
        m = FIFOMatcher()
        m.process_fill("BTC-USD", "buy", 1.0, 100.0, 2.0)

        # Mark at 110, unrealized = (110-100)*1 - 2 = 8
        assert m.get_unrealized_pnl("BTC-USD", 110.0) == pytest.approx(8.0)

    def test_sell_more_than_bought(self):
        """Selling more than in lots should still work (short/unmatched)."""
        m = FIFOMatcher()
        m.process_fill("BTC-USD", "buy", 0.5, 100.0, 0.0)
        result = m.process_fill("BTC-USD", "sell", 1.0, 110.0, 0.0)

        assert result is not None
        # Only 0.5 matched: (110-100)*0.5 = 5
        assert result.realized_pnl == pytest.approx(5.0)

    def test_from_fills_classmethod(self):
        """Build matcher from fill dicts."""
        fills = [
            {"symbol": "BTC-USD", "side": "buy", "qty": 1.0, "price": 100.0, "fee": 0.5, "fill_id": "f1", "executed_at": "2026-01-01T00:00:00Z"},
            {"symbol": "BTC-USD", "side": "sell", "qty": 1.0, "price": 110.0, "fee": 0.5, "fill_id": "f2", "executed_at": "2026-01-02T00:00:00Z"},
        ]
        m = FIFOMatcher.from_fills(fills)

        assert m.get_realized_pnl("BTC-USD") == pytest.approx(9.0)  # 10 - 0.5 - 0.5
        assert m.get_total_fees("BTC-USD") == pytest.approx(1.0)

    def test_cost_basis_multiple_lots(self):
        """Average cost basis across multiple open lots."""
        m = FIFOMatcher()
        m.process_fill("ETH-USD", "buy", 2.0, 100.0, 0.0)
        m.process_fill("ETH-USD", "buy", 3.0, 150.0, 0.0)

        # Weighted avg: (2*100 + 3*150) / 5 = 650/5 = 130
        assert m.get_cost_basis("ETH-USD") == pytest.approx(130.0)
        assert m.get_open_qty("ETH-USD") == pytest.approx(5.0)

    def test_empty_matcher(self):
        """Empty matcher returns zeros."""
        m = FIFOMatcher()
        assert m.get_realized_pnl() == 0.0
        assert m.get_open_qty("BTC-USD") == 0.0
        assert m.get_cost_basis("BTC-USD") == 0.0
        assert m.get_unrealized_pnl("BTC-USD", 100.0) == 0.0
        assert m.get_total_fees() == 0.0
        assert m.get_all_symbols() == []

    def test_total_fees_tracking(self):
        """Total fees tracked across buys and sells."""
        m = FIFOMatcher()
        m.process_fill("BTC-USD", "buy", 1.0, 100.0, 0.5)
        m.process_fill("BTC-USD", "buy", 1.0, 110.0, 0.3)
        m.process_fill("BTC-USD", "sell", 1.0, 120.0, 0.7)

        assert m.get_total_fees("BTC-USD") == pytest.approx(1.5)
