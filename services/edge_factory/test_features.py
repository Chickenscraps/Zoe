"""Unit tests for Edge Factory feature computations."""
from __future__ import annotations

import math

from .features.attention import TrendMomentum3D, TrendZScore14D
from .features.microstructure import CorwinSchultzSpread, FundingRateBasis, OpenInterestChange24h
from .features.risk import ConsecutiveLossCount, DrawdownCurrent, PortfolioHeat
from .features.technical import ADXTrendStrength, EfficiencyRatio, GarmanKlassVol, RSIRegimeState, VWAPDistance
from .models import FeatureSnapshot


# ── Attention Features ────────────────────────────────────────


def test_trend_z_score_normal():
    feature = TrendZScore14D()
    # Flat interest at 50, then spike to 80
    series = [50] * 13 + [80]
    result = feature.compute({"interest_over_time": series})
    assert result is not None
    assert result > 1.5  # Significant spike


def test_trend_z_score_flat():
    feature = TrendZScore14D()
    series = [50] * 14
    result = feature.compute({"interest_over_time": series})
    assert result is not None
    assert abs(result) < 0.01  # No deviation


def test_trend_z_score_insufficient_data():
    feature = TrendZScore14D()
    result = feature.compute({"interest_over_time": [50, 60]})
    assert result is None  # Too few points


def test_trend_z_score_missing_key():
    feature = TrendZScore14D()
    result = feature.compute({})
    assert result is None


def test_trend_momentum_positive():
    feature = TrendMomentum3D()
    series = [30, 35, 40, 50, 70]
    result = feature.compute({"interest_over_time": series})
    assert result is not None
    assert result > 0  # Growing interest


def test_trend_momentum_negative():
    feature = TrendMomentum3D()
    series = [70, 60, 50, 40, 30]
    result = feature.compute({"interest_over_time": series})
    assert result is not None
    assert result < 0  # Declining interest


def test_trend_momentum_insufficient():
    feature = TrendMomentum3D()
    result = feature.compute({"interest_over_time": [50, 60]})
    assert result is None


# ── Microstructure Features ───────────────────────────────────


def test_funding_rate_passthrough():
    feature = FundingRateBasis()
    result = feature.compute({"funding_rate": 0.0001})
    assert result == 0.0001


def test_funding_rate_negative():
    feature = FundingRateBasis()
    result = feature.compute({"funding_rate": -0.0003})
    assert result == -0.0003


def test_funding_rate_missing():
    feature = FundingRateBasis()
    result = feature.compute({})
    assert result is None


def test_corwin_schultz_with_bars():
    feature = CorwinSchultzSpread()
    # Create 10 bars with known high/low spread
    bars = []
    for i in range(10):
        base = 100 + i * 0.5
        bars.append({
            "high": base + 0.5,
            "low": base - 0.5,
            "close": base,
            "open": base - 0.1,
        })
    result = feature.compute({"bars_daily": bars})
    assert result is not None
    assert result >= 0  # Spread can't be negative


def test_corwin_schultz_insufficient():
    feature = CorwinSchultzSpread()
    result = feature.compute({"bars_daily": [{"high": 100, "low": 99}]})
    assert result is None


def test_open_interest_change_with_history():
    feature = OpenInterestChange24h()
    history = [FeatureSnapshot(symbol="BTC-USD", feature_name="open_interest_change_24h", value=1000.0)]
    result = feature.compute({"open_interest": 1100.0}, history=history)
    assert result is not None
    assert abs(result - 0.1) < 0.001  # 10% increase


def test_open_interest_change_no_history():
    feature = OpenInterestChange24h()
    result = feature.compute({"open_interest": 1000.0})
    assert result == 0.0  # Default when no history


# ── Technical Features ────────────────────────────────────────


def test_garman_klass_vol():
    feature = GarmanKlassVol()
    bars = []
    for i in range(30):
        base = 100
        bars.append({
            "open": base - 1,
            "high": base + 2,
            "low": base - 2,
            "close": base + 0.5,
        })
    result = feature.compute({"bars_daily": bars})
    assert result is not None
    assert result > 0  # Volatility must be positive


def test_garman_klass_insufficient():
    feature = GarmanKlassVol()
    result = feature.compute({"bars_daily": [{"open": 100, "high": 101, "low": 99, "close": 100}]})
    assert result is None


def test_rsi_oversold():
    feature = RSIRegimeState()
    # Create a strong downtrend for RSI < 30
    bars = []
    price = 100
    for i in range(20):
        bars.append({"close": price})
        price -= 2  # Strong decline
    result = feature.compute({"bars_daily": bars})
    assert result is not None
    assert result == 0.0  # Oversold


def test_rsi_overbought():
    feature = RSIRegimeState()
    # Create a strong uptrend for RSI > 70
    bars = []
    price = 100
    for i in range(20):
        bars.append({"close": price})
        price += 2  # Strong rally
    result = feature.compute({"bars_daily": bars})
    assert result is not None
    assert result == 1.0  # Overbought


def test_vwap_distance_above():
    feature = VWAPDistance()
    bars = [{"close": 100, "volume": 1000} for _ in range(5)]
    result = feature.compute({"bars_daily": bars, "current_price": 105})
    assert result is not None
    assert result > 0  # Above VWAP


def test_vwap_distance_below():
    feature = VWAPDistance()
    bars = [{"close": 100, "volume": 1000} for _ in range(5)]
    result = feature.compute({"bars_daily": bars, "current_price": 95})
    assert result is not None
    assert result < 0  # Below VWAP


def test_adx_trending():
    feature = ADXTrendStrength()
    # Create 30 bars with strong directional movement
    bars = []
    for i in range(30):
        base = 100 + i * 2  # Strong uptrend
        bars.append({
            "high": base + 1,
            "low": base - 0.5,
            "close": base,
        })
    result = feature.compute({"bars_daily": bars})
    assert result is not None
    assert result > 0.3  # Should show trending


def test_efficiency_ratio_perfect_trend():
    feature = EfficiencyRatio()
    bars = [{"close": 100 + i} for i in range(11)]  # Perfect uptrend
    result = feature.compute({"bars_daily": bars})
    assert result is not None
    assert result > 0.9  # Near-perfect efficiency


def test_efficiency_ratio_noise():
    feature = EfficiencyRatio()
    # Oscillating price - high volatility, low direction
    bars = [{"close": 100 + (2 if i % 2 == 0 else -2)} for i in range(11)]
    result = feature.compute({"bars_daily": bars})
    assert result is not None
    assert result < 0.3  # Low efficiency = noise


# ── Risk Features ─────────────────────────────────────────────


def test_portfolio_heat_zero():
    feature = PortfolioHeat()
    result = feature.compute({"open_exposure_usd": 0, "account_equity": 150})
    assert result == 0.0


def test_portfolio_heat_full():
    feature = PortfolioHeat()
    result = feature.compute({"open_exposure_usd": 150, "account_equity": 150})
    assert result == 1.0


def test_drawdown_current_none():
    feature = DrawdownCurrent()
    result = feature.compute({"equity_hwm": 150, "account_equity": 150})
    assert result == 0.0


def test_drawdown_current_10pct():
    feature = DrawdownCurrent()
    result = feature.compute({"equity_hwm": 150, "account_equity": 135})
    assert result is not None
    assert abs(result - 0.1) < 0.001  # 10% drawdown


def test_consecutive_loss_count():
    feature = ConsecutiveLossCount()
    result = feature.compute({"consecutive_losses": 3})
    assert result == 3.0


def run_all_tests():
    """Run all feature tests and report results."""
    import sys
    tests = [
        v for k, v in globals().items()
        if k.startswith("test_") and callable(v)
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL {test.__name__}: {e}")

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
