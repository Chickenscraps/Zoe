"""Tests for Phase 4: Intraday day-trading add-on module."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import EdgeFactoryConfig
from .intraday.event_risk_guard import EventRiskGuard
from .intraday.execution_adapter import IntradayExecutionAdapter
from .intraday.intraday_signal_engine import IntradaySignalEngine
from .intraday.limit_chase_policy import LimitChasePolicy
from .intraday.regime_manager import IntradayRegime, IntradayRegimeManager
from .intraday.risk_overlays import RiskOverlays
from .models import EdgePosition
from .repository import InMemoryFeatureRepository


# ── IntradayRegimeManager Tests ────────────────────────────


def test_regime_off_when_disabled():
    """OFF when intraday_enabled=False."""
    config = EdgeFactoryConfig()
    config.intraday_enabled = False
    mgr = IntradayRegimeManager(config)

    state = mgr.evaluate({})
    assert state.regime == IntradayRegime.OFF


def test_regime_halt_on_high_volatility():
    """HALT when 24h range > threshold."""
    config = EdgeFactoryConfig()
    config.intraday_enabled = True
    config.intraday_vol_halt_range = 0.05
    mgr = IntradayRegimeManager(config)

    features = {"range_24h_pct": 0.08, "rsi_4h": 30.0, "funding_rate_8h": 0.0}
    state = mgr.evaluate(features)
    assert state.regime == IntradayRegime.HALT
    assert "vol_halt" in state.reason


def test_regime_halt_on_event_risk():
    """HALT when event risk guard blocks."""
    config = EdgeFactoryConfig()
    config.intraday_enabled = True
    mgr = IntradayRegimeManager(config)

    features = {"range_24h_pct": 0.02, "rsi_4h": 25.0, "funding_rate_8h": 0.0}
    state = mgr.evaluate(features, event_blocked=True)
    assert state.regime == IntradayRegime.HALT


def test_regime_defensive_sniper_on_low_rsi():
    """DEFENSIVE_SNIPER when RSI deeply oversold."""
    config = EdgeFactoryConfig()
    config.intraday_enabled = True
    config.intraday_rsi_bear = 28.0
    mgr = IntradayRegimeManager(config)

    features = {
        "range_24h_pct": 0.03,
        "rsi_4h": 22.0,
        "funding_rate_8h": 0.00001,
        "vwap_distance": -0.01,
        "liquidity_score": 0.0,
        "spread_pct": 0.002,
    }
    state = mgr.evaluate(features)
    assert state.regime == IntradayRegime.DEFENSIVE_SNIPER


def test_regime_relief_rally_on_negative_funding():
    """RELIEF_RALLY when funding negative + RSI low."""
    config = EdgeFactoryConfig()
    config.intraday_enabled = True
    config.intraday_rsi_bull = 40.0
    mgr = IntradayRegimeManager(config)

    features = {
        "range_24h_pct": 0.02,
        "rsi_4h": 35.0,
        "funding_rate_8h": -0.0001,
        "vwap_distance": -0.005,
        "liquidity_score": 0.0,
        "spread_pct": 0.002,
    }
    state = mgr.evaluate(features)
    assert state.regime == IntradayRegime.RELIEF_RALLY


def test_regime_trend_follow():
    """TREND_FOLLOW when price above EMA50, funding safe, RSI recovering."""
    config = EdgeFactoryConfig()
    config.intraday_enabled = True
    mgr = IntradayRegimeManager(config)

    features = {
        "range_24h_pct": 0.02,
        "rsi_4h": 45.0,
        "funding_rate_8h": 0.00005,
        "vwap_distance": 0.02,
        "liquidity_score": 0.0,
        "spread_pct": 0.002,
    }
    state = mgr.evaluate(features)
    assert state.regime == IntradayRegime.TREND_FOLLOW


def test_regime_allows_entries():
    """allows_entries() reflects current regime."""
    config = EdgeFactoryConfig()
    config.intraday_enabled = True
    mgr = IntradayRegimeManager(config)

    # DEFENSIVE_SNIPER allows entries
    mgr.evaluate({
        "range_24h_pct": 0.02, "rsi_4h": 20.0, "funding_rate_8h": 0.0,
        "vwap_distance": -0.01, "liquidity_score": 0.0, "spread_pct": 0.002,
    })
    assert mgr.allows_entries() is True

    # HALT blocks entries
    mgr.evaluate({"range_24h_pct": 0.10})
    assert mgr.allows_entries() is False


# ── IntradaySignalEngine Tests ─────────────────────────────


def test_sniper_signal_on_low_rsi():
    """Sniper signal generated when RSI < bear threshold and funding fearful."""
    config = EdgeFactoryConfig()
    config.intraday_rsi_bear = 28.0
    config.intraday_funding_buy_max = 0.00001
    engine = IntradaySignalEngine(config)

    features = {
        "rsi_4h": 22.0,
        "funding_rate_8h": 0.000005,
        "expected_move_pct": 0.06,
        "vwap_distance": -0.01,
    }
    sig = engine.evaluate("BTC-USD", features, IntradayRegime.DEFENSIVE_SNIPER)

    assert sig is not None
    assert sig.strategy == "sniper_mean_reversion"
    assert sig.side == "buy"
    assert sig.strength > 0


def test_sniper_blocked_high_rsi():
    """No sniper signal when RSI above threshold."""
    config = EdgeFactoryConfig()
    config.intraday_rsi_bear = 28.0
    engine = IntradaySignalEngine(config)

    features = {"rsi_4h": 35.0, "funding_rate_8h": 0.000005, "expected_move_pct": 0.06}
    sig = engine.evaluate("BTC-USD", features, IntradayRegime.DEFENSIVE_SNIPER)
    assert sig is None


def test_sniper_blocked_high_funding():
    """No sniper signal when funding is too high (crowded longs)."""
    config = EdgeFactoryConfig()
    config.intraday_funding_buy_max = 0.00001
    engine = IntradaySignalEngine(config)

    features = {"rsi_4h": 22.0, "funding_rate_8h": 0.001, "expected_move_pct": 0.06}
    sig = engine.evaluate("BTC-USD", features, IntradayRegime.DEFENSIVE_SNIPER)
    assert sig is None


def test_trend_follow_signal():
    """Trend follow signal when above EMA50 and conditions met."""
    config = EdgeFactoryConfig()
    engine = IntradaySignalEngine(config)

    features = {
        "rsi_4h": 50.0,
        "funding_rate_8h": 0.00005,
        "expected_move_pct": 0.06,
        "vwap_distance": 0.02,
    }
    sig = engine.evaluate("BTC-USD", features, IntradayRegime.TREND_FOLLOW)

    assert sig is not None
    assert sig.strategy == "intraday_trend_follow"


def test_no_signal_in_halt():
    """No signal generated during HALT."""
    config = EdgeFactoryConfig()
    engine = IntradaySignalEngine(config)

    features = {"rsi_4h": 20.0, "funding_rate_8h": 0.0, "expected_move_pct": 0.06}
    sig = engine.evaluate("BTC-USD", features, IntradayRegime.HALT)
    assert sig is None


# ── LimitChasePolicy Tests ─────────────────────────────────


def test_chase_schedule_strong_signal():
    """Strong signal produces 3-step chase schedule."""
    config = EdgeFactoryConfig()
    config.intraday_chase_step_pct = 0.0005
    config.intraday_chase_steps = 3
    config.intraday_max_cross_pct = 0.002
    policy = LimitChasePolicy(config)

    schedule = policy.compute_chase_schedule(bid_price=50000.0, signal_strength=0.8)

    assert len(schedule.steps) == 3
    assert schedule.initial_price == 50000.0
    # Step 1: 50000 * 1.0005 = 50025
    assert abs(schedule.steps[0] - 50025.0) < 1.0
    # Step 2: 50000 * 1.001 = 50050
    assert abs(schedule.steps[1] - 50050.0) < 1.0
    # Step 3: 50000 * 1.0015 = 50075
    assert abs(schedule.steps[2] - 50075.0) < 1.0
    # Max: 50000 * 1.002 = 50100
    assert schedule.max_price == 50000.0 * 1.002


def test_chase_schedule_weak_signal():
    """Weak signal produces no chase steps."""
    config = EdgeFactoryConfig()
    policy = LimitChasePolicy(config)

    schedule = policy.compute_chase_schedule(bid_price=50000.0, signal_strength=0.3)

    assert len(schedule.steps) == 0
    assert schedule.initial_price == 50000.0


def test_chase_never_exceeds_max():
    """Chase steps capped at max_cross_pct."""
    config = EdgeFactoryConfig()
    config.intraday_chase_step_pct = 0.005  # Very large steps
    config.intraday_chase_steps = 5
    config.intraday_max_cross_pct = 0.002  # But max cap is small
    policy = LimitChasePolicy(config)

    schedule = policy.compute_chase_schedule(bid_price=50000.0, signal_strength=0.9)

    max_allowed = 50000.0 * 1.002
    for step_price in schedule.steps:
        assert step_price <= max_allowed + 0.01


# ── EventRiskGuard Tests ───────────────────────────────────


def test_event_risk_blocks_during_window():
    """Blocked during event +/- 30 min window."""
    guard = EventRiskGuard(buffer_minutes=30)

    now = datetime.now(timezone.utc)
    guard.add_event(now + timedelta(minutes=10))

    blocked, reason = guard.is_high_impact_window(now)
    assert blocked is True
    assert "event" in reason


def test_event_risk_allows_outside_window():
    """Allowed when no events nearby."""
    guard = EventRiskGuard(buffer_minutes=30)

    now = datetime.now(timezone.utc)
    guard.add_event(now + timedelta(hours=2))

    blocked, _ = guard.is_high_impact_window(now)
    assert blocked is False


# ── RiskOverlays Tests ──────────────────────────────────────


def test_bullets_limit_blocks():
    """Bullets limit blocks after max entries in DEFENSIVE_SNIPER."""
    config = EdgeFactoryConfig()
    config.intraday_max_bullets_24h = 2
    repo = InMemoryFeatureRepository()

    # Add 2 recent BTC entries
    for i in range(2):
        repo.insert_position(EdgePosition(
            symbol="BTC-USD", entry_price=50000.0, size_usd=10.0,
            status="open", position_id="bullet%d" % i,
        ))

    overlays = RiskOverlays(config, repo)
    allowed, reason = overlays.check_all(
        "BTC-USD", IntradayRegime.DEFENSIVE_SNIPER, {}
    )
    assert allowed is False
    assert "bullets" in reason


def test_vol_halt_blocks():
    """Volatility halt blocks entries."""
    config = EdgeFactoryConfig()
    config.intraday_vol_halt_range = 0.05
    repo = InMemoryFeatureRepository()
    overlays = RiskOverlays(config, repo)

    allowed, reason = overlays.check_all(
        "BTC-USD", IntradayRegime.DEFENSIVE_SNIPER,
        {"range_24h_pct": 0.08},
    )
    assert allowed is False
    assert "vol_halt" in reason


def test_overlays_allow_normal():
    """Overlays pass when all conditions normal."""
    config = EdgeFactoryConfig()
    repo = InMemoryFeatureRepository()
    overlays = RiskOverlays(config, repo)

    allowed, reason = overlays.check_all(
        "BTC-USD", IntradayRegime.DEFENSIVE_SNIPER,
        {"range_24h_pct": 0.02, "liquidity_score": 0.0},
    )
    assert allowed is True
    assert reason == ""


# ── ExecutionAdapter Tests ──────────────────────────────────


def test_execution_adapter_prepares_order():
    """ExecutionAdapter produces valid order params."""
    config = EdgeFactoryConfig()
    config.intraday_enabled = True
    config.account_equity = 150.0
    config.intraday_rung_pct = 0.25
    repo = InMemoryFeatureRepository()

    mgr = IntradayRegimeManager(config)
    mgr.evaluate({
        "range_24h_pct": 0.02, "rsi_4h": 22.0, "funding_rate_8h": 0.0,
        "vwap_distance": -0.01, "liquidity_score": 0.0, "spread_pct": 0.002,
    })

    overlays = RiskOverlays(config, repo)
    chase = LimitChasePolicy(config)
    adapter = IntradayExecutionAdapter(config, repo, mgr, overlays, chase)

    from .intraday.intraday_signal_engine import IntradaySignal
    signal = IntradaySignal(
        symbol="BTC-USD",
        side="buy",
        strategy="sniper_mean_reversion",
        strength=0.7,
        expected_move_pct=0.05,
        tp_pct=0.045,
        sl_pct=0.03,
    )

    order = adapter.prepare_order(signal, bid_price=50000.0, features={"range_24h_pct": 0.02})
    assert order is not None
    assert order["symbol"] == "BTC-USD"
    assert order["size_usd"] == 25.0  # 150 * 0.25 = 37.5, capped at 25
    assert order["tp_price"] > 50000.0
    assert order["sl_price"] < 50000.0


# ── Test Runner ─────────────────────────────────────────


def run_all_tests():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print("  PASS %s" % test.__name__)
        except Exception as e:
            failed += 1
            print("  FAIL %s: %s" % (test.__name__, e))
    print("\nIntraday Tests: %d passed, %d failed" % (passed, failed))
    return failed == 0


if __name__ == "__main__":
    run_all_tests()
