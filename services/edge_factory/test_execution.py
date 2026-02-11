"""Tests for V2 execution quality layer: QuoteModel, ExecutionPolicy, OrderManager."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from .config import EdgeFactoryConfig
from .execution_policy import ExecutionMode, ExecutionPolicyEngine
from .order_manager import OrderManager, SlippageRecord
from .quote_model import Quote, QuoteModel


# ── Mock RH Client ──────────────────────────────────────────


class MockRHClient:
    """Minimal mock of RobinhoodCryptoClient for testing."""

    def __init__(self, bid: float = 100000.0, ask: float = 100100.0):
        self.bid = bid
        self.ask = ask
        self._order_counter = 0
        self._order_status = "filled"  # Controls what get_order returns
        self._fill_price: float | None = None
        self._placed_orders: list[dict] = []

    async def get_best_bid_ask(self, symbol: str) -> dict:
        return {
            "results": [{
                "bid_inclusive_of_sell_spread": str(self.bid),
                "ask_inclusive_of_buy_spread": str(self.ask),
            }]
        }

    async def place_order(self, **kwargs) -> dict:
        self._order_counter += 1
        self._placed_orders.append(kwargs)
        return {"id": f"mock-order-{self._order_counter}"}

    async def get_order(self, order_id: str) -> dict:
        return {"status": self._order_status, "price": str(self._fill_price or self.bid)}

    async def get_order_fills(self, order_id: str) -> dict:
        return {"results": [{"price": str(self._fill_price or self.bid), "quantity": "0.001"}]}


# ── QuoteModel Tests ────────────────────────────────────────


def test_quote_model_refresh_and_cache():
    """QuoteModel.refresh() populates cache with correct BBO."""
    config = EdgeFactoryConfig()
    rh = MockRHClient(bid=50000.0, ask=50100.0)
    qm = QuoteModel(rh, config)

    quote = asyncio.get_event_loop().run_until_complete(qm.refresh("BTC-USD"))

    assert quote.bid == 50000.0
    assert quote.ask == 50100.0
    assert abs(quote.mid - 50050.0) < 0.01
    assert quote.spread_abs == 100.0
    assert abs(quote.spread_pct - 100.0 / 50050.0) < 0.0001
    assert qm.history_count("BTC-USD") == 1


def test_quote_model_latest_returns_cached():
    """latest() returns most recent quote if not stale."""
    config = EdgeFactoryConfig()
    config.quote_stale_sec = 60  # Won't be stale
    rh = MockRHClient(bid=50000.0, ask=50100.0)
    qm = QuoteModel(rh, config)

    asyncio.get_event_loop().run_until_complete(qm.refresh("BTC-USD"))
    latest = qm.latest("BTC-USD")

    assert latest is not None
    assert latest.bid == 50000.0


def test_quote_model_staleness_detection():
    """is_stale() returns True when quote is old."""
    config = EdgeFactoryConfig()
    config.quote_stale_sec = 1  # Very short threshold
    rh = MockRHClient()
    qm = QuoteModel(rh, config)

    asyncio.get_event_loop().run_until_complete(qm.refresh("BTC-USD"))

    # Manually age the quote
    qm._cache["BTC-USD"][-1].timestamp = datetime.now(timezone.utc) - timedelta(seconds=5)

    assert qm.is_stale("BTC-USD") is True
    assert qm.latest("BTC-USD") is None  # Stale returns None


def test_quote_model_avg_spread():
    """avg_spread_pct() computes rolling average correctly."""
    config = EdgeFactoryConfig()
    rh = MockRHClient()
    qm = QuoteModel(rh, config)

    # Manually insert quotes with different spreads
    for spread in [0.001, 0.002, 0.003, 0.004]:
        q = Quote(
            symbol="BTC-USD", bid=100.0, ask=100.0 * (1 + spread),
            mid=100.0 * (1 + spread / 2), spread_abs=100.0 * spread,
            spread_pct=spread,
        )
        if "BTC-USD" not in qm._cache:
            from collections import deque
            qm._cache["BTC-USD"] = deque(maxlen=100)
        qm._cache["BTC-USD"].append(q)

    avg = qm.avg_spread_pct("BTC-USD", window=4)
    expected = (0.001 + 0.002 + 0.003 + 0.004) / 4
    assert abs(avg - expected) < 0.0001


def test_quote_model_no_data_returns_zero():
    """mid_price/bid_price return 0.0 when no data."""
    config = EdgeFactoryConfig()
    rh = MockRHClient()
    qm = QuoteModel(rh, config)

    assert qm.mid_price("BTC-USD") == 0.0
    assert qm.bid_price("BTC-USD") == 0.0
    assert qm.latest("BTC-USD") is None


# ── ExecutionPolicy Tests ───────────────────────────────────


def test_passive_policy_uses_bid():
    """PASSIVE entry limit_price == bid exactly."""
    config = EdgeFactoryConfig()
    ep = ExecutionPolicyEngine(config)
    quote = Quote(symbol="BTC-USD", bid=50000.0, ask=50100.0, mid=50050.0,
                  spread_abs=100.0, spread_pct=0.002)

    params = ep.compute_entry_params(quote, ExecutionMode.PASSIVE)

    assert params.limit_price == 50000.0
    assert params.mode == ExecutionMode.PASSIVE
    assert params.ttl_seconds == config.passive_ttl_sec
    assert params.max_retries == 2


def test_normal_policy_adds_buffer():
    """NORMAL entry limit_price > bid by dynamic buffer."""
    config = EdgeFactoryConfig()
    ep = ExecutionPolicyEngine(config)
    quote = Quote(symbol="BTC-USD", bid=50000.0, ask=50100.0, mid=50050.0,
                  spread_abs=100.0, spread_pct=0.002)

    params = ep.compute_entry_params(quote, ExecutionMode.NORMAL)

    # Buffer = max(0.0005, 0.5 * 0.002) = max(0.0005, 0.001) = 0.001
    expected_price = 50000.0 * (1.0 + 0.001)
    assert abs(params.limit_price - expected_price) < 0.01
    assert params.mode == ExecutionMode.NORMAL


def test_panic_exit_crosses_spread():
    """PANIC_EXIT sell limit_price < bid (aggressive)."""
    config = EdgeFactoryConfig()
    ep = ExecutionPolicyEngine(config)
    quote = Quote(symbol="BTC-USD", bid=50000.0, ask=50100.0, mid=50050.0,
                  spread_abs=100.0, spread_pct=0.002)

    params = ep.compute_exit_params(quote, "stop_loss")

    assert params.limit_price < 50000.0
    assert params.mode == ExecutionMode.PANIC_EXIT
    assert params.ttl_seconds == config.panic_ttl_sec


def test_normal_exit_mild_buffer():
    """Normal exit (take_profit) has small buffer below bid."""
    config = EdgeFactoryConfig()
    ep = ExecutionPolicyEngine(config)
    quote = Quote(symbol="BTC-USD", bid=50000.0, ask=50100.0, mid=50050.0,
                  spread_abs=100.0, spread_pct=0.002)

    params = ep.compute_exit_params(quote, "take_profit")

    assert params.limit_price < 50000.0
    assert params.limit_price > 49900.0  # Not as aggressive as panic
    assert params.mode == ExecutionMode.NORMAL


def test_choose_entry_mode_passive_on_strong_signal():
    """Strong signal + tight spread -> PASSIVE mode."""
    config = EdgeFactoryConfig()
    ep = ExecutionPolicyEngine(config)

    mode = ep.choose_entry_mode(signal_strength=0.8, spread_pct=0.002)
    assert mode == ExecutionMode.PASSIVE

    mode = ep.choose_entry_mode(signal_strength=0.5, spread_pct=0.002)
    assert mode == ExecutionMode.NORMAL

    mode = ep.choose_entry_mode(signal_strength=0.8, spread_pct=0.005)
    assert mode == ExecutionMode.NORMAL


# ── OrderManager Tests ──────────────────────────────────────


def test_slippage_calculation():
    """Slippage vs mid and BBO computed correctly."""
    config = EdgeFactoryConfig()
    rh = MockRHClient()
    qm = QuoteModel(rh, config)
    om = OrderManager(rh, qm, config)

    # Simulate a buy fill
    from .order_manager import OrderTicket
    ticket = OrderTicket(
        client_order_id="test",
        symbol="BTC-USD",
        side="buy",
        size_usd=15.0,
        limit_price=50050.0,
        ttl_seconds=60,
        max_retries=0,
        execution_mode=ExecutionMode.NORMAL,
        fill_price=50060.0,  # Filled slightly above mid
        reference_mid=50050.0,
        bid_at_submit=50000.0,
        ask_at_submit=50100.0,
    )

    om._record_slippage(ticket)

    assert len(om.slippage_history) == 1
    record = om.slippage_history[0]

    # Slippage vs mid: (50060 - 50050) / 50050 * 10000 = ~2.0 bps
    assert abs(record.slippage_vs_mid_bps - 2.0) < 0.1

    # Slippage vs BBO (ask): (50060 - 50100) / 50100 * 10000 = ~-8.0 bps (better than ask!)
    assert record.slippage_vs_bbo_bps < 0

    # Spread: (50100 - 50000) / 50050 * 10000 = ~20.0 bps
    assert abs(record.spread_at_submit_bps - 20.0) < 0.1


def test_slippage_gate_allows_normal():
    """Slippage gate allows trading when avg slippage is low."""
    config = EdgeFactoryConfig()
    config.max_avg_slippage_bps = 50.0
    rh = MockRHClient()
    qm = QuoteModel(rh, config)
    om = OrderManager(rh, qm, config)

    # Add a few low-slippage records
    for _ in range(5):
        om.slippage_history.append(SlippageRecord(
            symbol="BTC-USD", side="buy", reference_mid=50000.0,
            fill_price=50005.0, bid_at_submit=50000.0, ask_at_submit=50100.0,
            slippage_vs_mid_bps=1.0, slippage_vs_bbo_bps=-19.0,
            spread_at_submit_bps=20.0, execution_mode="normal",
        ))

    allowed, avg = om.check_slippage_gate()
    assert allowed is True
    assert avg == 1.0


def test_slippage_gate_blocks_high_slippage():
    """Slippage gate blocks when avg slippage exceeds threshold."""
    config = EdgeFactoryConfig()
    config.max_avg_slippage_bps = 10.0  # Very tight
    rh = MockRHClient()
    qm = QuoteModel(rh, config)
    om = OrderManager(rh, qm, config)

    for _ in range(5):
        om.slippage_history.append(SlippageRecord(
            symbol="BTC-USD", side="buy", reference_mid=50000.0,
            fill_price=50100.0, bid_at_submit=50000.0, ask_at_submit=50100.0,
            slippage_vs_mid_bps=20.0, slippage_vs_bbo_bps=0.0,
            spread_at_submit_bps=20.0, execution_mode="normal",
        ))

    allowed, avg = om.check_slippage_gate()
    assert allowed is False
    assert avg == 20.0


# ── Test Runner ─────────────────────────────────────────────


def run_all_tests():
    tests = [
        test_quote_model_refresh_and_cache,
        test_quote_model_latest_returns_cached,
        test_quote_model_staleness_detection,
        test_quote_model_avg_spread,
        test_quote_model_no_data_returns_zero,
        test_passive_policy_uses_bid,
        test_normal_policy_adds_buffer,
        test_panic_exit_crosses_spread,
        test_normal_exit_mild_buffer,
        test_choose_entry_mode_passive_on_strong_signal,
        test_slippage_calculation,
        test_slippage_gate_allows_normal,
        test_slippage_gate_blocks_high_slippage,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print("  PASS  %s" % test.__name__)
            passed += 1
        except Exception as e:
            print("  FAIL  %s: %s" % (test.__name__, e))
            failed += 1

    print("\nExecution Tests: %d passed, %d failed" % (passed, failed))
    return failed == 0


if __name__ == "__main__":
    run_all_tests()
