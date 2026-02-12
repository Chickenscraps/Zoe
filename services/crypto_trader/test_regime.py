"""Tests for market regime detection."""
import pytest
from services.crypto_trader.regime import detect_regime, MarketRegime


class TestDetectRegime:
    """Test the detect_regime function."""

    def test_bull_regime(self):
        """Strong uptrend with positive EMA cross = bull."""
        snapshot = {
            "volatility": 60,
            "trend_strength": 0.8,
            "trend_direction": 0.05,
            "ema_crossover": 0.3,
        }
        regime = detect_regime(snapshot)
        assert regime.regime == "bull"
        assert regime.rsi_oversold == 40.0
        assert regime.rsi_overbought == 90.0
        assert regime.confidence > 0

    def test_bear_regime(self):
        """Strong downtrend with negative EMA cross = bear."""
        snapshot = {
            "volatility": 60,
            "trend_strength": 0.8,
            "trend_direction": -0.05,
            "ema_crossover": -0.3,
        }
        regime = detect_regime(snapshot)
        assert regime.regime == "bear"
        assert regime.rsi_oversold == 10.0
        assert regime.rsi_overbought == 60.0

    def test_high_vol_regime_priority(self):
        """High volatility takes priority over trend."""
        snapshot = {
            "volatility": 150,
            "trend_strength": 0.9,
            "trend_direction": 0.1,
            "ema_crossover": 0.5,
        }
        regime = detect_regime(snapshot)
        assert regime.regime == "high_vol"
        assert regime.rsi_oversold == 20.0
        assert regime.rsi_overbought == 80.0

    def test_sideways_default(self):
        """Low trend strength = sideways."""
        snapshot = {
            "volatility": 40,
            "trend_strength": 0.2,
            "trend_direction": 0.01,
            "ema_crossover": 0.0,
        }
        regime = detect_regime(snapshot)
        assert regime.regime == "sideways"
        assert regime.rsi_oversold == 30.0
        assert regime.rsi_overbought == 70.0

    def test_missing_volatility(self):
        """Missing volatility data doesn't crash."""
        snapshot = {
            "trend_strength": 0.3,
            "trend_direction": 0.01,
        }
        regime = detect_regime(snapshot)
        assert regime.regime in ("bull", "bear", "sideways", "high_vol")

    def test_empty_snapshot(self):
        """Empty snapshot defaults to sideways."""
        regime = detect_regime({})
        assert regime.regime == "sideways"

    def test_market_regime_dataclass(self):
        """MarketRegime is frozen and has to_dict."""
        regime = MarketRegime("bull", 0.85, 40.0, 90.0)
        assert regime.regime == "bull"
        assert regime.confidence == 0.85
        d = regime.to_dict()
        assert d["regime"] == "bull"
        assert d["confidence"] == 0.85

    def test_confidence_bounded(self):
        """Confidence should be between 0 and 1."""
        snapshot = {
            "volatility": 300,  # extreme
            "trend_strength": 1.0,
            "trend_direction": 0.5,
            "ema_crossover": 1.0,
        }
        regime = detect_regime(snapshot)
        assert 0 <= regime.confidence <= 1.0

    def test_borderline_vol_100(self):
        """Volatility exactly at 100 doesn't trigger high_vol (needs > 100)."""
        snapshot = {
            "volatility": 100,
            "trend_strength": 0.3,
            "trend_direction": 0.01,
            "ema_crossover": 0.0,
        }
        regime = detect_regime(snapshot)
        assert regime.regime != "high_vol"

    def test_vol_101_triggers_high_vol(self):
        """Volatility just above 100 triggers high_vol."""
        snapshot = {
            "volatility": 101,
            "trend_strength": 0.3,
        }
        regime = detect_regime(snapshot)
        assert regime.regime == "high_vol"
