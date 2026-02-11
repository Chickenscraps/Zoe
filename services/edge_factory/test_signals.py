"""Unit tests for signal generation, position sizing, and exit logic."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import EdgeFactoryConfig
from .models import EdgePosition, RegimeState
from .position_sizer import PositionSizer
from .regime_detector import RegimeDetector
from .repository import InMemoryFeatureRepository
from .signal_generator import SignalGenerator


def _make_components():
    config = EdgeFactoryConfig()
    repo = InMemoryFeatureRepository()
    detector = RegimeDetector(config, repo)
    generator = SignalGenerator(config, detector)
    sizer = PositionSizer(config, repo)
    return config, repo, detector, generator, sizer


def _bull_regime() -> RegimeState:
    return RegimeState(regime="low_vol_bull", confidence=0.8)


def _crash_regime() -> RegimeState:
    return RegimeState(regime="high_vol_crash", confidence=0.9)


def _all_conditions_met() -> dict[str, float]:
    """Feature dict where all entry conditions pass."""
    return {
        "trend_z_score_14d": 1.5,
        "funding_rate_basis": 0.0001,
        "vwap_distance": 0.02,
        "corwin_schultz_spread": 0.003,
        "portfolio_heat": 0.2,
        "consecutive_loss_count": 0,
        "efficiency_ratio": 0.5,
    }


# ── Signal Generation ─────────────────────────────────────────


def test_all_conditions_met_generates_signal():
    _, _, _, gen, _ = _make_components()
    signal = gen.evaluate("BTC-USD", _all_conditions_met(), _bull_regime())
    assert signal is not None
    assert signal.direction == "long"
    assert signal.symbol == "BTC-USD"
    assert 0 < signal.strength <= 1.0


def test_crash_regime_blocks_signal():
    _, _, _, gen, _ = _make_components()
    signal = gen.evaluate("BTC-USD", _all_conditions_met(), _crash_regime())
    assert signal is None


def test_low_trend_z_blocks_signal():
    _, _, _, gen, _ = _make_components()
    features = _all_conditions_met()
    features["trend_z_score_14d"] = 0.3  # Below 0.8 threshold
    signal = gen.evaluate("BTC-USD", features, _bull_regime())
    assert signal is None


def test_high_funding_rate_blocks_signal():
    _, _, _, gen, _ = _make_components()
    features = _all_conditions_met()
    features["funding_rate_basis"] = 0.001  # Above 0.0005 threshold
    signal = gen.evaluate("BTC-USD", features, _bull_regime())
    assert signal is None


def test_below_vwap_blocks_signal():
    _, _, _, gen, _ = _make_components()
    features = _all_conditions_met()
    features["vwap_distance"] = -0.01  # Below VWAP
    signal = gen.evaluate("BTC-USD", features, _bull_regime())
    assert signal is None


def test_wide_spread_blocks_signal():
    _, _, _, gen, _ = _make_components()
    features = _all_conditions_met()
    features["corwin_schultz_spread"] = 0.01  # 1% spread > 0.6% threshold
    signal = gen.evaluate("BTC-USD", features, _bull_regime())
    assert signal is None


def test_high_heat_blocks_signal():
    _, _, _, gen, _ = _make_components()
    features = _all_conditions_met()
    features["portfolio_heat"] = 0.7  # 70% > 60% threshold
    signal = gen.evaluate("BTC-USD", features, _bull_regime())
    assert signal is None


def test_consecutive_losses_blocks_signal():
    _, _, _, gen, _ = _make_components()
    features = _all_conditions_met()
    features["consecutive_loss_count"] = 5  # > 4 threshold
    signal = gen.evaluate("BTC-USD", features, _bull_regime())
    assert signal is None


def test_transition_regime_allows_signal():
    _, _, _, gen, _ = _make_components()
    transition = RegimeState(regime="transition", confidence=0.5)
    signal = gen.evaluate("BTC-USD", _all_conditions_met(), transition)
    assert signal is not None  # Transition allows trading


def test_missing_optional_features_still_passes():
    _, _, _, gen, _ = _make_components()
    features = {
        "trend_z_score_14d": 1.5,
        # funding_rate_basis missing - gate skips (None check)
        # vwap_distance missing
        # corwin_schultz_spread missing
        "portfolio_heat": 0.2,
        "consecutive_loss_count": 0,
    }
    # With missing optional features (None), gates pass
    signal = gen.evaluate("BTC-USD", features, _bull_regime())
    assert signal is not None


# ── Position Sizing ───────────────────────────────────────────


def test_position_sizer_respects_cap():
    _, _, _, _, sizer = _make_components()
    signal_features = _all_conditions_met()
    signal_features["regime"] = _bull_regime()

    from .models import Signal
    signal = Signal(
        symbol="BTC-USD",
        direction="long",
        strength=0.9,
        regime=_bull_regime(),
        features=signal_features,
    )

    size, tp, sl = sizer.compute_size(signal, current_price=50000.0)

    # Max is min($150 * 15%, $25) = $22.50
    assert size <= 22.50
    assert size >= 1.0  # Minimum trade
    assert tp > 50000.0  # TP above entry
    assert sl < 50000.0  # SL below entry


def test_position_sizer_tp_sl_math():
    _, _, _, _, sizer = _make_components()
    from .models import Signal
    signal = Signal(
        symbol="ETH-USD",
        direction="long",
        strength=0.5,
        regime=_bull_regime(),
    )

    _, tp, sl = sizer.compute_size(signal, current_price=3000.0)

    # TP = 3000 * 1.04 = 3120
    assert abs(tp - 3120.0) < 0.01
    # SL = 3000 * 0.98 = 2940
    assert abs(sl - 2940.0) < 0.01


def test_transition_regime_reduces_size():
    _, _, _, _, sizer = _make_components()
    from .models import Signal

    bull_signal = Signal(symbol="BTC-USD", direction="long", strength=0.8, regime=_bull_regime())
    trans_signal = Signal(symbol="BTC-USD", direction="long", strength=0.8, regime=RegimeState(regime="transition", confidence=0.5))

    bull_size, _, _ = sizer.compute_size(bull_signal, 50000.0)
    trans_size, _, _ = sizer.compute_size(trans_signal, 50000.0)

    assert trans_size < bull_size  # Transition = 50% sizing multiplier


# ── Exit Logic ────────────────────────────────────────────────


def test_exit_take_profit():
    _, _, _, gen, _ = _make_components()
    pos = EdgePosition(
        symbol="BTC-USD", entry_price=50000, tp_price=52000, sl_price=49000,
        entry_time=datetime.now(timezone.utc), status="open",
    )
    reason = gen.check_exit(pos, current_price=52500, features={}, regime=_bull_regime())
    assert reason == "take_profit"


def test_exit_stop_loss():
    _, _, _, gen, _ = _make_components()
    pos = EdgePosition(
        symbol="BTC-USD", entry_price=50000, tp_price=52000, sl_price=49000,
        entry_time=datetime.now(timezone.utc), status="open",
    )
    reason = gen.check_exit(pos, current_price=48500, features={}, regime=_bull_regime())
    assert reason == "stop_loss"


def test_exit_timeout():
    config, _, _, gen, _ = _make_components()
    pos = EdgePosition(
        symbol="BTC-USD", entry_price=50000, tp_price=52000, sl_price=49000,
        entry_time=datetime.now(timezone.utc) - timedelta(hours=49),  # > 48h
        status="open",
    )
    reason = gen.check_exit(pos, current_price=50100, features={}, regime=_bull_regime())
    assert reason == "timeout"


def test_exit_regime_change():
    _, _, _, gen, _ = _make_components()
    pos = EdgePosition(
        symbol="BTC-USD", entry_price=50000, tp_price=52000, sl_price=49000,
        entry_time=datetime.now(timezone.utc), status="open",
    )
    reason = gen.check_exit(pos, current_price=50500, features={}, regime=_crash_regime())
    assert reason == "regime_change"


def test_no_exit_in_range():
    _, _, _, gen, _ = _make_components()
    pos = EdgePosition(
        symbol="BTC-USD", entry_price=50000, tp_price=52000, sl_price=49000,
        entry_time=datetime.now(timezone.utc), status="open",
    )
    reason = gen.check_exit(pos, current_price=50500, features={}, regime=_bull_regime())
    assert reason is None


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
