"""Multi-timeframe (MTF) trend agreement analysis.

Checks trend direction across 15m, 1h, 4h timeframes and scores
alignment. When all timeframes agree on direction, the signal is
strongest. Mixed signals reduce confidence.

Uses candle-based EMAs and RSI per timeframe to determine trend.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .candle_manager import CandleManager


@dataclass
class TimeframeTrend:
    """Trend analysis for a single timeframe."""
    timeframe: str
    trend: str      # "bullish" | "bearish" | "neutral"
    strength: float  # 0.0 - 1.0
    rsi: float | None
    ema_fast: float | None
    ema_slow: float | None
    momentum: float | None  # % change over recent candles

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "trend": self.trend,
            "strength": round(self.strength, 3),
            "rsi": round(self.rsi, 1) if self.rsi is not None else None,
            "ema_fast": round(self.ema_fast, 2) if self.ema_fast is not None else None,
            "ema_slow": round(self.ema_slow, 2) if self.ema_slow is not None else None,
            "momentum": round(self.momentum, 4) if self.momentum is not None else None,
        }


@dataclass
class MTFResult:
    """Multi-timeframe analysis result for a symbol."""
    symbol: str
    alignment_score: float   # -1.0 (all bearish) to +1.0 (all bullish)
    dominant_trend: str      # "bullish" | "bearish" | "neutral"
    timeframes: list[TimeframeTrend]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "alignment_score": round(self.alignment_score, 3),
            "dominant_trend": self.dominant_trend,
            "timeframes": [tf.to_dict() for tf in self.timeframes],
        }


# ── Candle-based indicators ─────────────────────────────────────

def _ema_from_closes(closes: list[float], span: int) -> float | None:
    """Compute EMA from a list of close prices."""
    if len(closes) < span:
        return None
    alpha = 2.0 / (span + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = alpha * price + (1 - alpha) * ema
    return ema


def _rsi_from_closes(closes: list[float], period: int = 14) -> float | None:
    """Compute RSI from a list of close prices."""
    if len(closes) < period + 1:
        return None

    # Use only last period+1 prices
    prices = closes[-(period + 1):]
    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _momentum_from_closes(closes: list[float], lookback: int = 6) -> float | None:
    """% change over last `lookback` candle closes."""
    if len(closes) < lookback + 1:
        return None
    old = closes[-(lookback + 1)]
    new = closes[-1]
    if old == 0:
        return None
    return ((new - old) / old) * 100


# ── Timeframe trend analysis ────────────────────────────────────

# EMA spans per timeframe (in candle counts)
_TF_CONFIG = {
    "15m": {"ema_fast": 8, "ema_slow": 21, "rsi_period": 14, "min_candles": 22, "mom_lookback": 4},
    "1h":  {"ema_fast": 8, "ema_slow": 21, "rsi_period": 14, "min_candles": 22, "mom_lookback": 6},
    "4h":  {"ema_fast": 8, "ema_slow": 21, "rsi_period": 14, "min_candles": 22, "mom_lookback": 6},
}


def analyze_timeframe(candle_manager: CandleManager, symbol: str, timeframe: str) -> TimeframeTrend:
    """Analyze trend for a single symbol/timeframe pair."""
    cfg = _TF_CONFIG.get(timeframe, _TF_CONFIG["1h"])
    closes = candle_manager.get_closes(symbol, timeframe)

    if len(closes) < cfg["min_candles"]:
        return TimeframeTrend(
            timeframe=timeframe,
            trend="neutral",
            strength=0.0,
            rsi=None,
            ema_fast=None,
            ema_slow=None,
            momentum=None,
        )

    ema_fast = _ema_from_closes(closes, cfg["ema_fast"])
    ema_slow = _ema_from_closes(closes, cfg["ema_slow"])
    rsi = _rsi_from_closes(closes, cfg["rsi_period"])
    momentum = _momentum_from_closes(closes, cfg["mom_lookback"])

    # Determine trend direction
    trend = "neutral"
    strength = 0.0

    if ema_fast is not None and ema_slow is not None and ema_slow > 0:
        ema_diff_pct = ((ema_fast - ema_slow) / ema_slow) * 100

        if ema_diff_pct > 0.05:
            trend = "bullish"
            strength = min(1.0, ema_diff_pct * 2)
        elif ema_diff_pct < -0.05:
            trend = "bearish"
            strength = min(1.0, abs(ema_diff_pct) * 2)
        else:
            trend = "neutral"
            strength = 0.1

        # RSI confirmation
        if rsi is not None:
            if rsi > 55 and trend == "bullish":
                strength = min(1.0, strength + 0.15)
            elif rsi < 45 and trend == "bearish":
                strength = min(1.0, strength + 0.15)
            elif rsi > 70:
                # Overbought weakens bullish
                if trend == "bullish":
                    strength *= 0.7
            elif rsi < 30:
                # Oversold weakens bearish
                if trend == "bearish":
                    strength *= 0.7

        # Momentum confirmation
        if momentum is not None:
            if (momentum > 0 and trend == "bullish") or (momentum < 0 and trend == "bearish"):
                strength = min(1.0, strength + 0.1)

    return TimeframeTrend(
        timeframe=timeframe,
        trend=trend,
        strength=round(strength, 3),
        rsi=rsi,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        momentum=momentum,
    )


def analyze_mtf(candle_manager: CandleManager, symbol: str) -> MTFResult:
    """Full multi-timeframe analysis for a symbol.

    Analyzes 15m, 1h, and 4h timeframes and computes an alignment score.

    Returns:
        MTFResult with alignment_score from -1.0 (strongly bearish) to +1.0 (strongly bullish).
    """
    timeframes = ["15m", "1h", "4h"]
    tf_results: list[TimeframeTrend] = []

    for tf in timeframes:
        tf_results.append(analyze_timeframe(candle_manager, symbol, tf))

    # Compute alignment score
    # Weight: 4h (0.5) > 1h (0.3) > 15m (0.2) — higher timeframes more significant
    weights = {"15m": 0.2, "1h": 0.3, "4h": 0.5}
    alignment = 0.0

    for tf_trend in tf_results:
        w = weights.get(tf_trend.timeframe, 0.33)
        if tf_trend.trend == "bullish":
            alignment += w * tf_trend.strength
        elif tf_trend.trend == "bearish":
            alignment -= w * tf_trend.strength
        # neutral contributes 0

    alignment = max(-1.0, min(1.0, alignment))

    # Dominant trend
    if alignment > 0.15:
        dominant = "bullish"
    elif alignment < -0.15:
        dominant = "bearish"
    else:
        dominant = "neutral"

    return MTFResult(
        symbol=symbol,
        alignment_score=alignment,
        dominant_trend=dominant,
        timeframes=tf_results,
    )
