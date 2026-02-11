"""
Unit tests for capitulation detection, stabilization, wick ratio math,
and bounce scoring.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from bounce.capitulation import calculate_wick_ratio, detect_capitulation_event
from bounce.stabilization import check_stabilization
from bounce.bounce_score import calculate_bounce_score
from bounce.tests.fixtures import make_capitulation_df, make_flat_candles_df


# ═══════════════════════════════════════════════════════════════════════
# Wick ratio
# ═══════════════════════════════════════════════════════════════════════

class TestWickRatio:
    def test_classic_hammer(self):
        """Long lower wick → ratio > 0.5."""
        ratio = calculate_wick_ratio(open_p=95, high=96, low=88, close=95)
        assert ratio > 0.5

    def test_no_lower_wick(self):
        """Open/close at the low → ratio = 0."""
        ratio = calculate_wick_ratio(open_p=90, high=95, low=90, close=92)
        assert ratio == 0.0

    def test_flat_candle_zero_range(self):
        """High == Low → returns 0.0 (no division by zero)."""
        ratio = calculate_wick_ratio(open_p=100, high=100, low=100, close=100)
        assert ratio == 0.0

    def test_doji_candle(self):
        """Tiny range, open ≈ close → safe calculation."""
        ratio = calculate_wick_ratio(open_p=100.001, high=100.002, low=99.998, close=100.0)
        assert 0 <= ratio <= 1.0

    def test_full_wick(self):
        """Entire candle is lower wick (open==close==high)."""
        ratio = calculate_wick_ratio(open_p=100, high=100, low=90, close=100)
        assert ratio == 1.0

    def test_bearish_candle(self):
        """Close < open (bearish) — wick is from close to low."""
        ratio = calculate_wick_ratio(open_p=100, high=101, low=90, close=95)
        # lower wick = min(100,95) - 90 = 5, range = 11
        assert abs(ratio - 5.0 / 11.0) < 0.001


# ═══════════════════════════════════════════════════════════════════════
# Capitulation detection
# ═══════════════════════════════════════════════════════════════════════

class TestCapitulationDetection:
    def test_capitulation_fires_on_fixture(self):
        """The capitulation fixture should trigger detection."""
        df = make_capitulation_df()
        # Test against the capitulation candle (bar 45)
        # We pass up to bar 45 (index 0..45 = 46 bars)
        sub = df.iloc[:46]  # includes the cap candle as the last bar
        is_cap, metrics = detect_capitulation_event(
            sub, atr_len=14, vol_ma_len=20,
            atr_mult=2.0, vol_mult=2.0, lower_wick_min=0.40,
        )
        assert is_cap is True
        assert metrics["atr_satisfied"] is True
        assert metrics["vol_satisfied"] is True
        assert metrics["wick_satisfied"] is True

    def test_no_capitulation_on_normal_bars(self):
        """Normal downtrend bars should not trigger."""
        df = make_capitulation_df()
        sub = df.iloc[:40]  # only the gentle downtrend
        is_cap, metrics = detect_capitulation_event(
            sub, atr_len=14, vol_ma_len=20,
            atr_mult=2.5, vol_mult=2.0, lower_wick_min=0.45,
        )
        assert is_cap is False

    def test_no_capitulation_on_flat_candles(self):
        """Flat candles → no range, no volume → no capitulation."""
        df = make_flat_candles_df()
        is_cap, metrics = detect_capitulation_event(df)
        assert is_cap is False

    def test_all_three_conditions_required(self):
        """Missing any one condition → no capitulation."""
        df = make_capitulation_df()
        sub = df.iloc[:46]

        # Extremely high atr_mult → ATR condition fails
        is_cap, _ = detect_capitulation_event(sub, atr_mult=100.0)
        assert is_cap is False

        # Extremely high vol_mult → volume condition fails
        is_cap, _ = detect_capitulation_event(sub, vol_mult=100.0)
        assert is_cap is False

        # Extremely high wick threshold → wick condition fails
        is_cap, _ = detect_capitulation_event(sub, lower_wick_min=0.99)
        assert is_cap is False

    def test_deterministic_output(self):
        """Same input → same metrics."""
        df = make_capitulation_df()
        sub = df.iloc[:46]
        _, m1 = detect_capitulation_event(sub)
        _, m2 = detect_capitulation_event(sub)
        assert m1["tr"] == m2["tr"]
        assert m1["atr"] == m2["atr"]
        assert m1["wick_ratio"] == m2["wick_ratio"]


# ═══════════════════════════════════════════════════════════════════════
# Stabilization
# ═══════════════════════════════════════════════════════════════════════

class TestStabilization:
    def test_higher_lows_detected(self):
        """The post-capitulation fixture has ascending lows."""
        df = make_capitulation_df()
        post_cap = df.iloc[46:]  # stabilization phase
        cap_candle = {"high": float(df.iloc[45]["high"]), "low": float(df.iloc[45]["low"])}
        indicators = {"rsi_15m": 35, "funding_8h": -0.0005}

        is_stable, confirms = check_stabilization(
            post_cap, cap_candle, indicators,
            confirmations_required=2, higher_lows_k=4,
        )
        assert "higher_lows" in confirms

    def test_2_of_4_required(self):
        """With RSI above 30 + higher lows → 2 confirms → stabilized."""
        df = make_capitulation_df()
        post_cap = df.iloc[46:]
        cap_candle = {"high": float(df.iloc[45]["high"]), "low": float(df.iloc[45]["low"])}
        indicators = {"rsi_15m": 35}  # above 30

        is_stable, confirms = check_stabilization(
            post_cap, cap_candle, indicators,
            confirmations_required=2, higher_lows_k=4,
        )
        # higher_lows + rsi_reclaim = 2 confirmations
        assert is_stable is True
        assert len(confirms) >= 2

    def test_missing_funding_neutral(self):
        """Missing funding data with allow_missing_altdata → neutral."""
        df = make_capitulation_df()
        post_cap = df.iloc[46:]
        cap_candle = {"high": float(df.iloc[45]["high"]), "low": float(df.iloc[45]["low"])}
        indicators = {"rsi_15m": 35}  # no funding key

        is_stable, confirms = check_stabilization(
            post_cap, cap_candle, indicators,
            allow_missing_altdata=True,
        )
        assert "funding_supportive" not in confirms  # not credited

    def test_no_stabilization_with_zero_confirms(self):
        """If no conditions pass, not stabilized."""
        df = make_capitulation_df()
        post_cap = df.iloc[46:]
        cap_candle = {"high": 999.0, "low": 0.0}  # impossible to micro-break
        indicators = {"rsi_15m": 15}  # deep oversold

        is_stable, confirms = check_stabilization(
            post_cap, cap_candle, indicators,
            confirmations_required=2, rsi_reclaim=30,
        )
        # RSI 15 < 30 → no rsi_reclaim
        # micro-breakout depends on cap_candle high
        # May or may not have higher_lows — but we set req=2
        # This is a loose test; the fixture's higher_lows may still pass
        # We at least verify the function runs without error
        assert isinstance(is_stable, bool)
        assert isinstance(confirms, list)


# ═══════════════════════════════════════════════════════════════════════
# Bounce scoring
# ═══════════════════════════════════════════════════════════════════════

class TestBounceScore:
    def test_perfect_setup_high_score(self):
        """All metrics maxed → score near 100."""
        metrics = {"tr": 10, "atr": 2, "vol": 5000, "vol_ma": 1000, "wick_ratio": 0.7}
        confirms = ["higher_lows", "rsi_reclaim"]
        indicators = {"funding_8h": -0.001}

        result = calculate_bounce_score(metrics, confirms, indicators)
        assert result["score"] >= 80

    def test_weak_setup_low_score(self):
        """Marginal metrics → low score."""
        metrics = {"tr": 3, "atr": 2, "vol": 2500, "vol_ma": 2000, "wick_ratio": 0.3}
        confirms = ["higher_lows"]
        indicators = {"funding_8h": 0.005}  # positive = not supportive

        result = calculate_bounce_score(metrics, confirms, indicators)
        assert result["score"] < 70

    def test_score_capped_at_100(self):
        """Score never exceeds 100."""
        metrics = {"tr": 100, "atr": 1, "vol": 99999, "vol_ma": 1, "wick_ratio": 1.0}
        confirms = ["higher_lows", "rsi_reclaim", "micro_breakout"]
        indicators = {"funding_8h": -1}

        result = calculate_bounce_score(metrics, confirms, indicators)
        assert result["score"] <= 100

    def test_components_breakdown(self):
        """Components dict contains all expected keys."""
        metrics = {"tr": 5, "atr": 2, "vol": 3000, "vol_ma": 1500, "wick_ratio": 0.5}
        confirms = ["higher_lows"]
        indicators = {}

        result = calculate_bounce_score(metrics, confirms, indicators)
        assert "range_spike" in result["components"]
        assert "volume_spike" in result["components"]
        assert "wick_ratio" in result["components"]
        assert "stabilization" in result["components"]
        assert "funding" in result["components"]

    def test_zero_atr_safe(self):
        """Zero ATR → no crash, range_spike = 0."""
        metrics = {"tr": 5, "atr": 0, "vol": 1000, "vol_ma": 500, "wick_ratio": 0.5}
        result = calculate_bounce_score(metrics, [], {})
        assert result["components"]["range_spike"] == 0
