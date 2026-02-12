"""Market regime detection for adaptive indicator thresholds.

Identifies the current market regime to dynamically adjust RSI
overbought/oversold thresholds and other indicator parameters.

Research (Table 2) shows that rigid RSI thresholds (30/70) fail in
trending markets:
  - Bull market:  RSI stays 40-90 for months; 70 is NOT overbought
  - Bear market:  RSI stays 10-60; 30 is NOT necessarily oversold
  - Sideways:     standard 30/70 works well
  - High vol:     widen to 20/80 to avoid noise-triggered entries

Regime detection combines trend strength, direction, EMA crossover,
and realized volatility from the existing indicator stack.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ── Regime thresholds (from research Table 2) ──────────────────

_RSI_THRESHOLDS: dict[str, tuple[float, float]] = {
    "bull":     (40.0, 90.0),
    "bear":     (10.0, 60.0),
    "sideways": (30.0, 70.0),
    "high_vol": (20.0, 80.0),
}


@dataclass(frozen=True)
class MarketRegime:
    """Current market regime with adaptive thresholds."""

    regime: str        # "bull" | "bear" | "sideways" | "high_vol"
    confidence: float  # 0.0-1.0 how confident the regime classification is
    rsi_oversold: float
    rsi_overbought: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "confidence": round(self.confidence, 2),
            "rsi_oversold": self.rsi_oversold,
            "rsi_overbought": self.rsi_overbought,
        }


def detect_regime(snapshot: dict[str, Any]) -> MarketRegime:
    """Detect current market regime from a price cache snapshot.

    Uses:
        - volatility (annualized %) — high vol regime takes priority
        - trend_strength (R² 0-1) — distinguishes trending vs sideways
        - trend_direction (% per tick) — bull vs bear
        - ema_crossover (fast-slow spread %) — confirms trend direction

    Returns MarketRegime with appropriate RSI thresholds.
    """
    vol = snapshot.get("volatility")
    trend_str = snapshot.get("trend_strength", 0) or 0
    trend_dir = snapshot.get("trend_direction", 0) or 0
    ema_cross = snapshot.get("ema_crossover", 0) or 0

    # High volatility regime takes priority (>100% annualized)
    if vol is not None and vol > 100:
        conf = min(1.0, vol / 150)
        os, ob = _RSI_THRESHOLDS["high_vol"]
        return MarketRegime("high_vol", conf, os, ob)

    # Bull regime: strong uptrend confirmed by EMA
    if trend_str > 0.5 and trend_dir > 0 and ema_cross > 0:
        conf = min(1.0, trend_str * 0.7 + min(ema_cross, 0.5) * 0.6)
        os, ob = _RSI_THRESHOLDS["bull"]
        return MarketRegime("bull", conf, os, ob)

    # Bear regime: strong downtrend confirmed by EMA
    if trend_str > 0.5 and trend_dir < 0 and ema_cross < 0:
        conf = min(1.0, trend_str * 0.7 + min(abs(ema_cross), 0.5) * 0.6)
        os, ob = _RSI_THRESHOLDS["bear"]
        return MarketRegime("bear", conf, os, ob)

    # Default: sideways / ranging
    conf = max(0.3, 1.0 - trend_str)
    os, ob = _RSI_THRESHOLDS["sideways"]
    return MarketRegime("sideways", conf, os, ob)
