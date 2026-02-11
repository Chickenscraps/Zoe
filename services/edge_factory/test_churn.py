"""Tests for V2 churn control: Amihud features, ExpectedMove, TradeIntentBuilder, AccountState."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from .account_state import AccountState
from .config import EdgeFactoryConfig
from .features.liquidity import AmihudIlliquidity, AmihudSpikeDetector
from .features.volatility import ExpectedMovePct
from .models import EdgePosition, RegimeState, Signal
from .position_sizer import PositionSizer
from .repository import InMemoryFeatureRepository
from .trade_intent import TradeIntentBuilder


def _make_bars(n: int = 30, base_price: float = 100.0, vol_factor: float = 0.02) -> list[dict]:
    """Generate n daily OHLCV bars with moderate volatility."""
    bars = []
    price = base_price
    for i in range(n):
        move = vol_factor * price * (1 if i % 3 != 0 else -1)
        o = price
        h = price + abs(move) * 1.2
        l = price - abs(move) * 0.5
        c = price + move
        v = 1_000_000 + i * 10000
        bars.append({"open": o, "high": h, "low": l, "close": c, "volume": v})
        price = c
    return bars


def _make_illiquid_bars(n: int = 30) -> list[dict]:
    """Bars with very low volume (illiquid market)."""
    bars = []
    price = 100.0
    for i in range(n):
        move = 0.05 * price * (1 if i % 2 == 0 else -1)
        o = price
        h = price + abs(move) * 1.5
        l = price - abs(move) * 0.5
        c = price + move
        v = 100  # Very low volume
        bars.append({"open": o, "high": h, "low": l, "close": c, "volume": v})
        price = c
    return bars


# ── Amihud Illiquidity Tests ──────────────────────────────


def test_amihud_illiquidity_normal_market():
    """Amihud computes correctly with normal volume bars."""
    feature = AmihudIlliquidity()
    bars = _make_bars(30)
    result = feature.compute({"bars_daily": bars})

    assert result is not None
    assert result > 0
    assert result < 1e-6  # Normal market should have very small ratio


def test_amihud_illiquidity_low_volume():
    """Illiquid bars produce much higher Amihud ratio."""
    feature = AmihudIlliquidity()
    bars = _make_illiquid_bars(30)
    result = feature.compute({"bars_daily": bars})

    assert result is not None
    # Low volume = high Amihud
    normal_bars = _make_bars(30)
    normal_result = feature.compute({"bars_daily": normal_bars})
    assert result > normal_result * 10  # Much more illiquid


def test_amihud_insufficient_data():
    """Returns None with insufficient bars."""
    feature = AmihudIlliquidity()
    result = feature.compute({"bars_daily": _make_bars(5)})
    assert result is None


def test_amihud_spike_normal():
    """Spike z-score near zero in normal market."""
    feature = AmihudSpikeDetector()
    bars = _make_bars(30)
    result = feature.compute({"bars_daily": bars})

    assert result is not None
    # In a normal market, z-score should be modest
    assert abs(result) < 3.0


def test_amihud_spike_detects_liquidity_hole():
    """Spike z-score > 2.0 when last bar has extreme illiquidity."""
    feature = AmihudSpikeDetector()
    # Normal bars except last one has very low volume
    bars = _make_bars(30)
    bars[-1]["volume"] = 10  # Liquidity hole
    bars[-1]["close"] = bars[-1]["close"] * 1.10  # Big move + no volume

    result = feature.compute({"bars_daily": bars})
    assert result is not None
    assert result > 2.0  # Should trigger crash regime


# ── ExpectedMove Tests ────────────────────────────────────


def test_expected_move_moderate_vol():
    """Expected move computes correctly from GK vol."""
    feature = ExpectedMovePct()
    bars = _make_bars(30, vol_factor=0.02)
    result = feature.compute({"bars_daily": bars})

    assert result is not None
    assert result >= 0.003  # Min clamp 0.3%
    assert result <= 0.15   # Max clamp 15%


def test_expected_move_clamps_low():
    """Very low vol clamped to MIN_MOVE."""
    feature = ExpectedMovePct()
    # Nearly flat bars
    bars = []
    for i in range(30):
        bars.append({"open": 100.0, "high": 100.01, "low": 99.99, "close": 100.0, "volume": 1000000})
    result = feature.compute({"bars_daily": bars})

    assert result is not None
    assert result >= 0.003  # Clamped to min


def test_expected_move_insufficient():
    """Returns None with insufficient bars."""
    feature = ExpectedMovePct()
    result = feature.compute({"bars_daily": _make_bars(5)})
    assert result is None


# ── TradeIntentBuilder Tests ──────────────────────────────


def _make_signal(symbol: str = "BTC-USD", strength: float = 0.8) -> Signal:
    return Signal(
        symbol=symbol,
        direction="long",
        strength=strength,
        regime=RegimeState(regime="low_vol_bull", confidence=0.8),
        features={"trend_z_score_14d": 1.0, "funding_rate_basis": 0.0001},
    )


def test_trade_intent_builds_valid():
    """TradeIntentBuilder produces valid intent when all gates pass."""
    config = EdgeFactoryConfig()
    repo = InMemoryFeatureRepository()
    sizer = PositionSizer(config, repo)
    builder = TradeIntentBuilder(config, sizer, repo)

    signal = _make_signal()
    features = {"expected_move_pct": 0.05}
    intent = builder.build(signal, features, current_price=50000.0)

    assert intent is not None
    assert intent.symbol == "BTC-USD"
    assert intent.size_usd > 0
    assert intent.tp_price > 50000.0
    assert intent.sl_price < 50000.0
    assert intent.expected_move_pct == 0.05
    assert intent.churn_cleared is True


def test_trade_intent_blocked_no_expected_move():
    """Blocked when expected_move_pct is missing."""
    config = EdgeFactoryConfig()
    repo = InMemoryFeatureRepository()
    sizer = PositionSizer(config, repo)
    builder = TradeIntentBuilder(config, sizer, repo)

    signal = _make_signal()
    intent = builder.build(signal, {}, current_price=50000.0)
    assert intent is None


def test_trade_intent_blocked_low_expected_move():
    """Blocked when expected_move < min threshold."""
    config = EdgeFactoryConfig()
    config.min_expected_move_pct = 0.04  # 4%
    repo = InMemoryFeatureRepository()
    sizer = PositionSizer(config, repo)
    builder = TradeIntentBuilder(config, sizer, repo)

    signal = _make_signal()
    features = {"expected_move_pct": 0.02}  # Only 2% expected
    intent = builder.build(signal, features, current_price=50000.0)
    assert intent is None


def test_trade_intent_blocked_concentration():
    """Blocked when symbol already has open position."""
    config = EdgeFactoryConfig()
    repo = InMemoryFeatureRepository()

    # Insert an open position for BTC-USD
    repo.insert_position(EdgePosition(
        symbol="BTC-USD",
        entry_price=50000.0,
        size_usd=15.0,
        status="open",
        position_id="existing",
    ))

    sizer = PositionSizer(config, repo)
    builder = TradeIntentBuilder(config, sizer, repo)

    signal = _make_signal()
    features = {"expected_move_pct": 0.05}
    intent = builder.build(signal, features, current_price=50000.0)
    assert intent is None  # Blocked: concentration


def test_trade_intent_blocked_cooldown():
    """Blocked when symbol was recently traded."""
    config = EdgeFactoryConfig()
    config.symbol_cooldown_hours = 4
    repo = InMemoryFeatureRepository()

    # Insert a recently closed position
    repo.insert_position(EdgePosition(
        symbol="BTC-USD",
        entry_price=50000.0,
        size_usd=15.0,
        status="closed_tp",
        exit_price=52000.0,
        exit_time=datetime.now(timezone.utc) - timedelta(hours=1),
        pnl_usd=0.60,
        position_id="recent",
    ))

    sizer = PositionSizer(config, repo)
    builder = TradeIntentBuilder(config, sizer, repo)

    signal = _make_signal()
    features = {"expected_move_pct": 0.05}
    intent = builder.build(signal, features, current_price=50000.0)
    assert intent is None  # Blocked: cooldown


def test_trade_intent_blocked_low_equity():
    """Blocked when remaining equity is too low."""
    config = EdgeFactoryConfig()
    config.account_equity = 20.0  # Small account
    config.min_remaining_equity = 10.0
    repo = InMemoryFeatureRepository()

    # Open positions eat up most equity
    repo.insert_position(EdgePosition(
        symbol="ETH-USD", entry_price=3000.0, size_usd=12.0,
        status="open", position_id="pos1",
    ))

    sizer = PositionSizer(config, repo)
    builder = TradeIntentBuilder(config, sizer, repo)

    signal = _make_signal()
    features = {"expected_move_pct": 0.05}
    intent = builder.build(signal, features, current_price=50000.0)
    assert intent is None  # Blocked: remaining equity


# ── AccountState Tests ────────────────────────────────────


def test_account_state_paper_equity():
    """Paper equity = base + realized PnL."""
    import asyncio

    config = EdgeFactoryConfig()
    config.account_equity = 150.0
    repo = InMemoryFeatureRepository()

    # Add some closed positions with PnL
    repo.insert_position(EdgePosition(
        symbol="BTC-USD", entry_price=50000.0, size_usd=15.0,
        status="closed_tp", pnl_usd=2.50, position_id="win1",
        exit_time=datetime.now(timezone.utc),
    ))
    repo.insert_position(EdgePosition(
        symbol="ETH-USD", entry_price=3000.0, size_usd=10.0,
        status="closed_sl", pnl_usd=-1.00, position_id="loss1",
        exit_time=datetime.now(timezone.utc),
    ))

    acct = AccountState(config, repo)
    equity = asyncio.get_event_loop().run_until_complete(acct.refresh())

    # 150 + 2.50 - 1.00 = 151.50
    assert abs(equity - 151.50) < 0.01


def test_account_state_available_cash():
    """Available cash = equity - open exposure."""
    config = EdgeFactoryConfig()
    config.account_equity = 150.0
    repo = InMemoryFeatureRepository()

    repo.insert_position(EdgePosition(
        symbol="BTC-USD", entry_price=50000.0, size_usd=20.0,
        status="open", position_id="open1",
    ))

    acct = AccountState(config, repo)
    cash = acct.available_cash()
    assert abs(cash - 130.0) < 0.01


# ── Regime Detector Amihud Integration ────────────────────


def test_amihud_spike_triggers_crash_regime():
    """amihud_spike_z > 2.0 triggers HIGH_VOL_CRASH regime."""
    from .regime_detector import RegimeDetector

    config = EdgeFactoryConfig()
    repo = InMemoryFeatureRepository()
    detector = RegimeDetector(config, repo)

    # Normal features except amihud spike is elevated
    features = {
        "garman_klass_vol": 0.5,
        "adx_trend_strength": 0.4,
        "drawdown_current": 0.05,
        "vwap_distance": 0.01,
        "rsi_regime_state": 0.5,
        "amihud_spike_z": 2.5,  # Liquidity hole!
    }

    regime = detector.detect(features)
    assert regime.regime == "high_vol_crash"


def test_normal_amihud_does_not_crash():
    """Normal amihud_spike_z does not trigger crash."""
    from .regime_detector import RegimeDetector

    config = EdgeFactoryConfig()
    repo = InMemoryFeatureRepository()
    detector = RegimeDetector(config, repo)

    features = {
        "garman_klass_vol": 0.5,
        "adx_trend_strength": 0.4,
        "drawdown_current": 0.05,
        "vwap_distance": 0.01,
        "rsi_regime_state": 0.5,
        "amihud_spike_z": 0.5,  # Normal
    }

    regime = detector.detect(features)
    assert regime.regime != "high_vol_crash"


# ── Test Runner ─────────────────────────────────────────


def run_all_tests():
    tests = [
        test_amihud_illiquidity_normal_market,
        test_amihud_illiquidity_low_volume,
        test_amihud_insufficient_data,
        test_amihud_spike_normal,
        test_amihud_spike_detects_liquidity_hole,
        test_expected_move_moderate_vol,
        test_expected_move_clamps_low,
        test_expected_move_insufficient,
        test_trade_intent_builds_valid,
        test_trade_intent_blocked_no_expected_move,
        test_trade_intent_blocked_low_expected_move,
        test_trade_intent_blocked_concentration,
        test_trade_intent_blocked_cooldown,
        test_trade_intent_blocked_low_equity,
        test_account_state_paper_equity,
        test_account_state_available_cash,
        test_amihud_spike_triggers_crash_regime,
        test_normal_amihud_does_not_crash,
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

    print("\nChurn Tests: %d passed, %d failed" % (passed, failed))
    return failed == 0


if __name__ == "__main__":
    run_all_tests()
