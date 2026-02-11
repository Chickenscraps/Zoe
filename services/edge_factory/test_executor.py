"""Unit tests for paper executor."""
from __future__ import annotations

import asyncio

from .config import EdgeFactoryConfig
from .models import EdgePosition, RegimeState, Signal
from .paper_executor import PaperExecutor
from .repository import InMemoryFeatureRepository


def _make_executor():
    config = EdgeFactoryConfig()
    repo = InMemoryFeatureRepository()
    return PaperExecutor(config, repo), repo


def _make_signal(symbol: str = "BTC-USD") -> Signal:
    return Signal(
        symbol=symbol,
        direction="long",
        strength=0.7,
        regime=RegimeState(regime="low_vol_bull", confidence=0.8),
        signal_id="test-signal-001",
    )


def test_paper_entry_creates_position():
    executor, repo = _make_executor()
    signal = _make_signal()

    position_id = asyncio.get_event_loop().run_until_complete(
        executor.submit_entry(signal, size_usd=15.0, limit_price=50000.0, tp_price=52000.0, sl_price=49000.0)
    )

    assert position_id
    open_pos = repo.get_open_positions()
    assert len(open_pos) == 1
    pos = open_pos[0]
    assert pos.symbol == "BTC-USD"
    assert pos.size_usd == 15.0
    assert pos.status == "open"
    assert pos.tp_price == 52000.0
    assert pos.sl_price == 49000.0


def test_paper_entry_pessimistic_fill():
    executor, repo = _make_executor()
    signal = _make_signal()

    asyncio.get_event_loop().run_until_complete(
        executor.submit_entry(signal, size_usd=10.0, limit_price=50000.0, tp_price=52000.0, sl_price=49000.0)
    )

    pos = repo.get_open_positions()[0]
    # Pessimistic: entry_price > limit_price (by spread + slippage)
    assert pos.entry_price > 50000.0
    expected_friction = 50000.0 * (0.003 + 0.0005)  # spread + slippage
    assert abs(pos.entry_price - (50000.0 + expected_friction)) < 0.01


def test_paper_exit_stop_loss():
    executor, repo = _make_executor()
    signal = _make_signal()

    asyncio.get_event_loop().run_until_complete(
        executor.submit_entry(signal, size_usd=10.0, limit_price=50000.0, tp_price=52000.0, sl_price=49000.0)
    )

    pos = repo.get_open_positions()[0]

    asyncio.get_event_loop().run_until_complete(
        executor.submit_exit(pos, "stop_loss", current_price=48500.0)
    )

    closed = repo.get_closed_positions()
    assert len(closed) == 1
    assert closed[0].status == "closed_sl"
    assert closed[0].pnl_usd is not None
    assert closed[0].pnl_usd < 0  # Loss


def test_paper_exit_take_profit():
    executor, repo = _make_executor()
    signal = _make_signal()

    asyncio.get_event_loop().run_until_complete(
        executor.submit_entry(signal, size_usd=10.0, limit_price=50000.0, tp_price=52000.0, sl_price=49000.0)
    )

    pos = repo.get_open_positions()[0]

    asyncio.get_event_loop().run_until_complete(
        executor.submit_exit(pos, "take_profit", current_price=52500.0)
    )

    closed = repo.get_closed_positions()
    assert len(closed) == 1
    assert closed[0].status == "closed_tp"
    assert closed[0].pnl_usd is not None
    assert closed[0].pnl_usd > 0  # Profit


def test_paper_exit_pessimistic_fill():
    executor, repo = _make_executor()
    signal = _make_signal()

    asyncio.get_event_loop().run_until_complete(
        executor.submit_entry(signal, size_usd=10.0, limit_price=50000.0, tp_price=52000.0, sl_price=49000.0)
    )

    pos = repo.get_open_positions()[0]

    asyncio.get_event_loop().run_until_complete(
        executor.submit_exit(pos, "take_profit", current_price=52000.0)
    )

    closed = repo.get_closed_positions()[0]
    # Exit price should be BELOW current_price (pessimistic sell)
    assert closed.exit_price < 52000.0


def test_multiple_positions():
    executor, repo = _make_executor()

    for sym in ["BTC-USD", "ETH-USD", "SOL-USD"]:
        signal = _make_signal(sym)
        asyncio.get_event_loop().run_until_complete(
            executor.submit_entry(signal, size_usd=10.0, limit_price=100.0, tp_price=104.0, sl_price=98.0)
        )

    assert len(repo.get_open_positions()) == 3


def run_all_tests():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL {test.__name__}: {e}")
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_all_tests() else 1)
