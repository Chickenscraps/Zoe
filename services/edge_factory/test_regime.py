"""Unit tests for regime detection."""
from __future__ import annotations

from .config import EdgeFactoryConfig
from .regime_detector import RegimeDetector
from .repository import InMemoryFeatureRepository


def _make_detector() -> RegimeDetector:
    config = EdgeFactoryConfig()
    repo = InMemoryFeatureRepository()
    return RegimeDetector(config, repo)


def test_low_vol_bull():
    detector = _make_detector()
    features = {
        "garman_klass_vol": 0.4,      # 40% annualized - moderate
        "adx_trend_strength": 0.5,    # Trending
        "drawdown_current": 0.02,     # 2% drawdown - fine
        "vwap_distance": 0.02,        # Above VWAP
        "rsi_regime_state": 0.5,      # Neutral RSI
        "efficiency_ratio": 0.5,      # Decent efficiency
    }
    regime = detector.detect(features)
    assert regime.regime == "low_vol_bull"
    assert regime.allows_trading()
    assert regime.sizing_multiplier() == 1.0


def test_high_vol_crash_by_volatility():
    detector = _make_detector()
    features = {
        "garman_klass_vol": 1.5,      # 150% annualized - extreme
        "adx_trend_strength": 0.2,
        "drawdown_current": 0.05,
        "vwap_distance": -0.05,
    }
    regime = detector.detect(features)
    assert regime.regime == "high_vol_crash"
    assert not regime.allows_trading()
    assert regime.sizing_multiplier() == 0.0


def test_high_vol_crash_by_drawdown():
    detector = _make_detector()
    features = {
        "garman_klass_vol": 0.5,
        "adx_trend_strength": 0.3,
        "drawdown_current": 0.25,     # 25% drawdown > 20% threshold
        "vwap_distance": 0.01,
    }
    regime = detector.detect(features)
    assert regime.regime == "high_vol_crash"


def test_transition_no_trend():
    detector = _make_detector()
    features = {
        "garman_klass_vol": 0.4,
        "adx_trend_strength": 0.15,   # No trend (below 0.3)
        "drawdown_current": 0.05,
        "vwap_distance": 0.01,
    }
    regime = detector.detect(features)
    assert regime.regime == "transition"
    assert regime.allows_trading()  # Transition allows trading
    assert regime.sizing_multiplier() == 0.5  # But at reduced size


def test_transition_bearish():
    detector = _make_detector()
    features = {
        "garman_klass_vol": 0.3,
        "adx_trend_strength": 0.5,    # Trending
        "drawdown_current": 0.03,
        "vwap_distance": -0.02,       # Below VWAP - bearish
    }
    regime = detector.detect(features)
    assert regime.regime == "transition"


def test_should_trade_gating():
    detector = _make_detector()

    bull = detector.detect({"garman_klass_vol": 0.3, "adx_trend_strength": 0.5, "vwap_distance": 0.02, "drawdown_current": 0.01})
    assert detector.should_trade(bull)

    crash = detector.detect({"garman_klass_vol": 1.5, "drawdown_current": 0.01})
    assert not detector.should_trade(crash)


def test_regime_persistence():
    config = EdgeFactoryConfig()
    repo = InMemoryFeatureRepository()
    detector = RegimeDetector(config, repo)

    features = {"garman_klass_vol": 0.3, "adx_trend_strength": 0.5, "vwap_distance": 0.02, "drawdown_current": 0.01}
    regime = detector.detect(features)
    regime_id = detector.persist(regime)

    latest = repo.get_latest_regime()
    assert latest is not None
    assert latest.regime == "low_vol_bull"


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
