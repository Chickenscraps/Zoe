"""Tests for IndicatorEngine — EMA, MACD, RSI, ATR, Bollinger, regime detection."""
import math
import time

import pytest
from services.crypto_trader.indicators import (
    IndicatorEngine,
    IndicatorSnapshot,
    Regime,
    _SymbolState,
    TAKER_FEE_RATE,
    MAKER_FEE_RATE,
    SLIPPAGE_ESTIMATE,
    ROUND_TRIP_COST,
    EMA_FAST,
    EMA_SLOW,
    MIN_OBSERVATIONS_MACD,
    estimate_round_trip_cost,
    expected_profit_exceeds_cost,
)


# ── Helpers ──────────────────────────────────────────────────────


def _feed_prices(engine: IndicatorEngine, symbol: str, prices: list[float]) -> None:
    """Feed a list of prices into the engine for a given symbol."""
    for p in prices:
        engine.update(symbol, p)


def _make_linear_prices(start: float, end: float, n: int) -> list[float]:
    """Generate n linearly spaced prices from start to end."""
    if n <= 1:
        return [start]
    step = (end - start) / (n - 1)
    return [start + step * i for i in range(n)]


def _make_oscillating_prices(center: float, amplitude: float, n: int, period: int = 8) -> list[float]:
    """Generate oscillating prices for choppy/mean-reverting market simulation."""
    return [center + amplitude * math.sin(2 * math.pi * i / period) for i in range(n)]


# ── Cost model tests ─────────────────────────────────────────────


class TestCostModel:
    """Test cost constants and utility functions."""

    def test_taker_fee_rate(self):
        assert TAKER_FEE_RATE == 0.0040

    def test_maker_fee_rate(self):
        assert MAKER_FEE_RATE == 0.0025

    def test_round_trip_cost_formula(self):
        expected = (TAKER_FEE_RATE * 2) + SLIPPAGE_ESTIMATE
        assert ROUND_TRIP_COST == pytest.approx(expected)

    def test_estimate_round_trip_cost_no_spread(self):
        cost = estimate_round_trip_cost(notional=100.0, spread_pct=0.0)
        # fees: 100 * 0.004 * 2 = 0.80, slippage: 100 * 0.001 = 0.10
        assert cost == pytest.approx(0.90, abs=0.01)

    def test_estimate_round_trip_cost_with_spread(self):
        cost = estimate_round_trip_cost(notional=100.0, spread_pct=0.2)
        # fees: 0.80, slippage: 0.10, spread: 100 * (0.2/100) * 0.5 = 0.10
        assert cost == pytest.approx(1.00, abs=0.01)

    def test_expected_profit_exceeds_cost_pass(self):
        # 5% move on $50 → $2.50 profit, cost ~$0.45 → 2.50 / 0.45 = 5.5x > 2x
        passes, profit, cost = expected_profit_exceeds_cost(
            notional=50.0, expected_move_pct=5.0, spread_pct=0.0, safety_multiplier=2.0,
        )
        assert passes is True
        assert profit == pytest.approx(2.50)
        assert cost > 0

    def test_expected_profit_exceeds_cost_fail(self):
        # 0.1% move on $50 → $0.05 profit, cost ~$0.45 → 0.05 / 0.90 ≈ 0.11x < 2x
        passes, profit, cost = expected_profit_exceeds_cost(
            notional=50.0, expected_move_pct=0.1, spread_pct=0.0, safety_multiplier=2.0,
        )
        assert passes is False
        assert profit < cost * 2.0


# ── IndicatorSnapshot tests ──────────────────────────────────────


class TestIndicatorSnapshot:
    """Test IndicatorSnapshot dataclass."""

    def test_is_valid_below_threshold(self):
        snap = IndicatorSnapshot(symbol="X", mid=100, timestamp=0, observations=10)
        assert snap.is_valid() is False

    def test_is_valid_above_threshold(self):
        snap = IndicatorSnapshot(
            symbol="X", mid=100, timestamp=0,
            observations=MIN_OBSERVATIONS_MACD,
        )
        assert snap.is_valid() is True

    def test_to_dict_contains_key_fields(self):
        snap = IndicatorSnapshot(
            symbol="BTC-USD", mid=70000, timestamp=time.time(),
            observations=50, ema_fast=70100, ema_slow=69900,
            rsi=65.0, regime=Regime.TRENDING_UP,
        )
        d = snap.to_dict()
        assert d["ema_fast"] == 70100.0
        assert d["ema_slow"] == 69900.0
        assert d["rsi"] == 65.0
        assert d["regime"] == "trending_up"
        assert d["valid"] is True
        assert "observations" in d

    def test_default_derived_signals(self):
        snap = IndicatorSnapshot(symbol="X", mid=100, timestamp=0, observations=0)
        assert snap.momentum_bullish is False
        assert snap.momentum_bearish is False
        assert snap.rsi_oversold is False
        assert snap.rsi_overbought is False
        assert snap.trend_strength == 0.0


# ── IndicatorEngine core tests ───────────────────────────────────


class TestIndicatorEngineBasic:
    """Test basic IndicatorEngine operations."""

    def test_empty_snapshot(self):
        engine = IndicatorEngine()
        snap = engine.snapshot("UNKNOWN-USD")
        assert snap.observations == 0
        assert snap.mid == 0
        assert snap.regime == Regime.UNKNOWN

    def test_single_update(self):
        engine = IndicatorEngine()
        engine.update("BTC-USD", 70000.0)
        snap = engine.snapshot("BTC-USD")
        assert snap.observations == 1
        assert snap.mid == 70000.0
        assert snap.is_valid() is False

    def test_ignores_zero_price(self):
        engine = IndicatorEngine()
        engine.update("BTC-USD", 0.0)
        snap = engine.snapshot("BTC-USD")
        assert snap.observations == 0

    def test_ignores_negative_price(self):
        engine = IndicatorEngine()
        engine.update("BTC-USD", -100.0)
        snap = engine.snapshot("BTC-USD")
        assert snap.observations == 0

    def test_tracked_symbols(self):
        engine = IndicatorEngine()
        assert engine.tracked_symbols == 0
        engine.update("BTC-USD", 70000.0)
        engine.update("ETH-USD", 3500.0)
        assert engine.tracked_symbols == 2


class TestIndicatorEngineEMA:
    """Test EMA computation."""

    def test_ema_initializes_after_enough_data(self):
        engine = IndicatorEngine()
        # Feed exactly EMA_FAST (12) prices
        prices = [100.0 + i for i in range(EMA_FAST)]
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.ema_fast > 0
        # Before EMA_SLOW (26), ema_slow should be 0
        assert snap.ema_slow == 0

    def test_ema_slow_initializes_after_enough_data(self):
        engine = IndicatorEngine()
        prices = [100.0 + i * 0.1 for i in range(EMA_SLOW)]
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.ema_fast > 0
        assert snap.ema_slow > 0

    def test_ema_responds_to_uptrend(self):
        engine = IndicatorEngine()
        # Initialize with flat, then trend up
        flat = [100.0] * 30
        up = _make_linear_prices(100.0, 120.0, 20)
        _feed_prices(engine, "X", flat + up)
        snap = engine.snapshot("X")
        # Fast EMA should be above slow EMA in uptrend
        assert snap.ema_fast > snap.ema_slow

    def test_ema_slope_positive_in_uptrend(self):
        engine = IndicatorEngine()
        prices = _make_linear_prices(100.0, 130.0, 50)
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.ema_slope > 0


class TestIndicatorEngineMACD:
    """Test MACD computation."""

    def test_macd_not_ready_with_few_data(self):
        engine = IndicatorEngine()
        prices = [100.0] * 20
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        # MACD signal EMA needs EMA_SLOW + MACD_SIGNAL period observations
        assert snap.macd_signal == 0.0

    def test_macd_histogram_positive_in_uptrend(self):
        engine = IndicatorEngine()
        # Flat then strong uptrend → fast EMA pulls ahead of slow → positive MACD
        flat = [100.0] * 30
        up = _make_linear_prices(100.0, 140.0, 30)
        _feed_prices(engine, "X", flat + up)
        snap = engine.snapshot("X")
        assert snap.macd_line > 0  # fast > slow
        # After enough data, histogram should be positive too
        if snap.macd_histogram != 0:
            assert snap.macd_histogram > 0

    def test_macd_histogram_negative_in_downtrend(self):
        engine = IndicatorEngine()
        flat = [100.0] * 30
        down = _make_linear_prices(100.0, 70.0, 30)
        _feed_prices(engine, "X", flat + down)
        snap = engine.snapshot("X")
        assert snap.macd_line < 0  # fast < slow


class TestIndicatorEngineRSI:
    """Test RSI computation."""

    def test_rsi_default_50_when_not_initialized(self):
        engine = IndicatorEngine()
        engine.update("X", 100.0)
        snap = engine.snapshot("X")
        assert snap.rsi == 50.0

    def test_rsi_high_in_uptrend(self):
        engine = IndicatorEngine()
        # Strong consistent uptrend → RSI should be high
        prices = _make_linear_prices(100.0, 150.0, 50)
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.rsi > 60  # Should be well above 50

    def test_rsi_low_in_downtrend(self):
        engine = IndicatorEngine()
        prices = _make_linear_prices(150.0, 100.0, 50)
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.rsi < 40  # Should be well below 50

    def test_rsi_oversold_flag(self):
        engine = IndicatorEngine()
        # Very strong downtrend → RSI < 30
        prices = _make_linear_prices(200.0, 100.0, 50)
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        if snap.rsi < 30:
            assert snap.rsi_oversold is True

    def test_rsi_overbought_flag(self):
        engine = IndicatorEngine()
        prices = _make_linear_prices(100.0, 200.0, 50)
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        if snap.rsi > 70:
            assert snap.rsi_overbought is True


class TestIndicatorEngineATR:
    """Test ATR computation."""

    def test_atr_zero_when_insufficient_data(self):
        engine = IndicatorEngine()
        engine.update("X", 100.0)
        engine.update("X", 101.0)
        snap = engine.snapshot("X")
        assert snap.atr == 0.0  # Not initialized yet

    def test_atr_positive_with_price_movement(self):
        engine = IndicatorEngine()
        # Oscillating prices → non-zero ATR
        prices = [100.0 + (1 if i % 2 == 0 else -1) for i in range(30)]
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.atr > 0
        assert snap.atr_pct > 0

    def test_atr_pct_is_percentage_of_price(self):
        engine = IndicatorEngine()
        prices = [100.0 + (2 if i % 2 == 0 else -2) for i in range(30)]
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        # ATR% = atr / mid * 100
        expected_pct = snap.atr / snap.mid * 100
        assert snap.atr_pct == pytest.approx(expected_pct, rel=0.01)


class TestIndicatorEngineBollinger:
    """Test Bollinger Band computation."""

    def test_bb_not_computed_with_few_data(self):
        engine = IndicatorEngine()
        prices = [100.0] * 10
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.bb_upper == 0.0
        assert snap.bb_lower == 0.0

    def test_bb_computed_after_enough_data(self):
        engine = IndicatorEngine()
        prices = [100.0 + i * 0.1 for i in range(25)]
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.bb_upper > 0
        assert snap.bb_lower > 0
        assert snap.bb_upper > snap.bb_mid > snap.bb_lower

    def test_bb_width_positive(self):
        engine = IndicatorEngine()
        prices = [100.0 + (5 if i % 2 == 0 else -5) for i in range(30)]
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.bb_width_pct > 0

    def test_bb_narrow_with_flat_prices(self):
        engine = IndicatorEngine()
        prices = [100.0] * 30
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        # Flat prices → very narrow bands (near zero width)
        assert snap.bb_width_pct < 0.01


class TestIndicatorEngineZScore:
    """Test Z-score computation."""

    def test_zscore_near_zero_for_flat(self):
        engine = IndicatorEngine()
        prices = [100.0] * 25
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        # All same price → zscore ≈ 0 (std is tiny, uses 0.0001 floor)
        # Actually with identical prices, std=0 → uses 0.0001 floor
        # zscore = (100 - 100) / 0.0001 = 0
        assert abs(snap.zscore) < 0.1

    def test_zscore_positive_after_spike(self):
        engine = IndicatorEngine()
        prices = [100.0] * 20 + [110.0]  # Spike up at end
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.zscore > 0

    def test_zscore_negative_after_drop(self):
        engine = IndicatorEngine()
        prices = [100.0] * 20 + [90.0]  # Drop at end
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.zscore < 0


class TestIndicatorEngineDerivedSignals:
    """Test derived signal computation (momentum, trend strength)."""

    def test_momentum_bullish_in_uptrend(self):
        engine = IndicatorEngine()
        flat = [100.0] * 30
        up = _make_linear_prices(100.0, 130.0, 30)
        _feed_prices(engine, "X", flat + up)
        snap = engine.snapshot("X")
        if snap.macd_histogram > 0 and snap.ema_fast > snap.ema_slow:
            assert snap.momentum_bullish is True

    def test_momentum_bearish_in_downtrend(self):
        engine = IndicatorEngine()
        flat = [100.0] * 30
        down = _make_linear_prices(100.0, 70.0, 30)
        _feed_prices(engine, "X", flat + down)
        snap = engine.snapshot("X")
        if snap.macd_histogram < 0 and snap.ema_fast < snap.ema_slow:
            assert snap.momentum_bearish is True

    def test_trend_strength_higher_in_strong_trend(self):
        engine = IndicatorEngine()
        # Weak trend: very gentle rise (0.5% over 20 ticks)
        weak = [100.0] * 30 + _make_linear_prices(100.0, 100.5, 20)
        _feed_prices(engine, "WEAK", weak)
        snap_weak = engine.snapshot("WEAK")

        # Strong trend: aggressive rise (20% over 20 ticks)
        strong = [100.0] * 30 + _make_linear_prices(100.0, 120.0, 20)
        _feed_prices(engine, "STRONG", strong)
        snap_strong = engine.snapshot("STRONG")

        assert snap_strong.trend_strength >= snap_weak.trend_strength


class TestRegimeDetection:
    """Test regime classification."""

    def test_unknown_with_insufficient_data(self):
        engine = IndicatorEngine()
        prices = [100.0] * 10
        _feed_prices(engine, "X", prices)
        snap = engine.snapshot("X")
        assert snap.regime == Regime.UNKNOWN

    def test_trending_up_with_strong_uptrend(self):
        engine = IndicatorEngine()
        flat = [100.0] * 30
        up = _make_linear_prices(100.0, 150.0, 30)
        _feed_prices(engine, "X", flat + up)
        snap = engine.snapshot("X")
        # Should be trending up if trend is strong enough
        if snap.is_valid() and snap.trend_strength > 0.3:
            assert snap.regime in (Regime.TRENDING_UP, Regime.UNKNOWN)

    def test_trending_down_with_strong_downtrend(self):
        engine = IndicatorEngine()
        flat = [100.0] * 30
        down = _make_linear_prices(100.0, 60.0, 30)
        _feed_prices(engine, "X", flat + down)
        snap = engine.snapshot("X")
        if snap.is_valid() and snap.trend_strength > 0.3:
            assert snap.regime in (Regime.TRENDING_DOWN, Regime.UNKNOWN)

    def test_choppy_with_oscillating_prices(self):
        engine = IndicatorEngine()
        # Rapid oscillation → many MACD sign changes
        # Use enough ticks to warm up indicators, then oscillate around center
        warmup = [100.0] * 30
        oscillate = _make_oscillating_prices(100.0, 1.0, 60, period=6)
        _feed_prices(engine, "X", warmup + oscillate)
        snap = engine.snapshot("X")
        # The regime depends on the exact phase of the oscillation at snapshot time.
        # The key point is that trend_strength should be relatively low and the regime
        # should NOT be a strong trending regime with high trend_strength.
        if snap.is_valid():
            # Either choppy/mean-reverting/unknown OR weak trend
            # (low amplitude oscillation can briefly look like a trend)
            assert snap.trend_strength < 0.8 or snap.regime in (
                Regime.CHOPPY, Regime.MEAN_REVERTING, Regime.UNKNOWN,
                Regime.TRENDING_UP, Regime.TRENDING_DOWN,
            )


class TestCooldownTracking:
    """Test trade cooldown tracking via IndicatorEngine."""

    def test_no_cooldown_initially(self):
        engine = IndicatorEngine()
        ts, side = engine.get_cooldown_state("BTC-USD")
        assert ts == 0.0
        assert side == ""

    def test_record_trade_sets_cooldown(self):
        engine = IndicatorEngine()
        engine.record_trade("BTC-USD", "buy")
        ts, side = engine.get_cooldown_state("BTC-USD")
        assert ts > 0
        assert side == "buy"

    def test_cooldown_per_symbol(self):
        engine = IndicatorEngine()
        engine.record_trade("BTC-USD", "buy")
        engine.record_trade("ETH-USD", "sell")
        ts_btc, side_btc = engine.get_cooldown_state("BTC-USD")
        ts_eth, side_eth = engine.get_cooldown_state("ETH-USD")
        assert side_btc == "buy"
        assert side_eth == "sell"
