"""Candlestick pattern detection — pure Python, no external deps.

Detects common reversal and continuation patterns from OHLCV candle arrays.
Each pattern returns a PatternMatch with name, direction, strength, and index.

Patterns detected:
  Bullish reversals: hammer, inverted_hammer, bullish_engulfing, morning_star,
                     three_white_soldiers, dragonfly_doji
  Bearish reversals: shooting_star, bearish_engulfing, evening_star,
                     three_black_crows, gravestone_doji
  Continuation:      doji, spinning_top

Also includes support/resistance level detection from swing highs/lows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .candle_manager import Candle


@dataclass(frozen=True)
class PatternMatch:
    """Detected candlestick pattern."""
    name: str
    direction: str   # "bullish" | "bearish" | "neutral"
    strength: float  # 0.0 - 1.0
    candle_index: int  # index in the input candle array

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "direction": self.direction,
            "strength": round(self.strength, 2),
            "candle_index": self.candle_index,
        }


@dataclass(frozen=True)
class SRLevel:
    """Support or resistance price level."""
    price: float
    level_type: str  # "support" | "resistance"
    strength: int    # number of touches
    last_touch_idx: int

    def to_dict(self) -> dict:
        return {
            "price": round(self.price, 2),
            "type": self.level_type,
            "strength": self.strength,
        }


# ── Helper functions ────────────────────────────────────────────

def _body(c: Candle) -> float:
    """Absolute body size."""
    return abs(c.close - c.open)


def _body_signed(c: Candle) -> float:
    """Signed body: positive = bullish, negative = bearish."""
    return c.close - c.open


def _range(c: Candle) -> float:
    """Total candle range (high - low)."""
    return c.high - c.low


def _upper_wick(c: Candle) -> float:
    return c.high - max(c.open, c.close)


def _lower_wick(c: Candle) -> float:
    return min(c.open, c.close) - c.low


def _is_bullish(c: Candle) -> bool:
    return c.close > c.open


def _is_bearish(c: Candle) -> bool:
    return c.close < c.open


def _body_ratio(c: Candle) -> float:
    """Body as fraction of total range."""
    r = _range(c)
    return _body(c) / r if r > 0 else 0.0


def _avg_body(candles: list[Candle]) -> float:
    """Average body size of candles."""
    if not candles:
        return 0.0
    return sum(_body(c) for c in candles) / len(candles)


# ── Single-candle patterns ──────────────────────────────────────

def _detect_hammer(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Hammer: small body at top, long lower wick (≥2x body), short upper wick.
    Bullish reversal when it appears after a downtrend.
    """
    c = candles[idx]
    r = _range(c)
    if r == 0:
        return None
    body = _body(c)
    lw = _lower_wick(c)
    uw = _upper_wick(c)

    if body == 0:
        body = r * 0.001  # avoid division by zero

    if lw >= 2 * body and uw <= body * 0.5 and _body_ratio(c) < 0.4:
        # Check for preceding downtrend (last 3 candles)
        if idx >= 3:
            trend_down = candles[idx - 3].close > candles[idx - 1].close
        else:
            trend_down = True  # assume
        strength = min(1.0, (lw / body) / 4) * (0.8 if trend_down else 0.5)
        return PatternMatch("hammer", "bullish", strength, idx)
    return None


def _detect_inverted_hammer(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Inverted hammer: small body at bottom, long upper wick, short lower wick."""
    c = candles[idx]
    r = _range(c)
    if r == 0:
        return None
    body = _body(c)
    lw = _lower_wick(c)
    uw = _upper_wick(c)

    if body == 0:
        body = r * 0.001

    if uw >= 2 * body and lw <= body * 0.5 and _body_ratio(c) < 0.4:
        strength = min(1.0, (uw / body) / 4) * 0.6
        return PatternMatch("inverted_hammer", "bullish", strength, idx)
    return None


def _detect_shooting_star(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Shooting star: small body at bottom, long upper wick after uptrend."""
    c = candles[idx]
    r = _range(c)
    if r == 0:
        return None
    body = _body(c)
    lw = _lower_wick(c)
    uw = _upper_wick(c)

    if body == 0:
        body = r * 0.001

    if uw >= 2 * body and lw <= body * 0.5 and _body_ratio(c) < 0.4:
        # Check for preceding uptrend
        if idx >= 3:
            trend_up = candles[idx - 3].close < candles[idx - 1].close
        else:
            trend_up = True
        strength = min(1.0, (uw / body) / 4) * (0.8 if trend_up else 0.5)
        return PatternMatch("shooting_star", "bearish", strength, idx)
    return None


def _detect_doji(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Doji: very small body relative to range — indecision."""
    c = candles[idx]
    r = _range(c)
    if r == 0:
        return None
    ratio = _body_ratio(c)
    if ratio < 0.1:
        # Classify sub-types
        uw = _upper_wick(c)
        lw = _lower_wick(c)
        if lw > 3 * uw and lw > 0:
            return PatternMatch("dragonfly_doji", "bullish", 0.6, idx)
        if uw > 3 * lw and uw > 0:
            return PatternMatch("gravestone_doji", "bearish", 0.6, idx)
        return PatternMatch("doji", "neutral", 0.4, idx)
    return None


def _detect_spinning_top(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Spinning top: small body with roughly equal upper and lower wicks."""
    c = candles[idx]
    r = _range(c)
    if r == 0:
        return None
    ratio = _body_ratio(c)
    uw = _upper_wick(c)
    lw = _lower_wick(c)

    if 0.1 <= ratio <= 0.35:
        min_wick = min(uw, lw)
        max_wick = max(uw, lw)
        if max_wick > 0 and min_wick / max_wick > 0.4:
            return PatternMatch("spinning_top", "neutral", 0.3, idx)
    return None


# ── Two-candle patterns ─────────────────────────────────────────

def _detect_bullish_engulfing(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Bullish engulfing: bearish candle followed by larger bullish candle."""
    if idx < 1:
        return None
    prev, curr = candles[idx - 1], candles[idx]
    if _is_bearish(prev) and _is_bullish(curr):
        if curr.open <= prev.close and curr.close >= prev.open:
            size_ratio = _body(curr) / (_body(prev) or 0.001)
            strength = min(1.0, size_ratio / 2) * 0.8
            return PatternMatch("bullish_engulfing", "bullish", strength, idx)
    return None


def _detect_bearish_engulfing(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Bearish engulfing: bullish candle followed by larger bearish candle."""
    if idx < 1:
        return None
    prev, curr = candles[idx - 1], candles[idx]
    if _is_bullish(prev) and _is_bearish(curr):
        if curr.open >= prev.close and curr.close <= prev.open:
            size_ratio = _body(curr) / (_body(prev) or 0.001)
            strength = min(1.0, size_ratio / 2) * 0.8
            return PatternMatch("bearish_engulfing", "bearish", strength, idx)
    return None


# ── Three-candle patterns ───────────────────────────────────────

def _detect_morning_star(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Morning star: bearish → small body (star) → bullish. Reversal up."""
    if idx < 2:
        return None
    first, star, third = candles[idx - 2], candles[idx - 1], candles[idx]

    if not _is_bearish(first):
        return None
    if not _is_bullish(third):
        return None
    # Star should have small body
    avg = _avg_body([first, third])
    if avg == 0:
        return None
    if _body(star) > avg * 0.4:
        return None
    # Third candle should close above first's midpoint
    first_mid = (first.open + first.close) / 2
    if third.close > first_mid:
        strength = min(1.0, _body(third) / avg) * 0.85
        return PatternMatch("morning_star", "bullish", strength, idx)
    return None


def _detect_evening_star(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Evening star: bullish → small body (star) → bearish. Reversal down."""
    if idx < 2:
        return None
    first, star, third = candles[idx - 2], candles[idx - 1], candles[idx]

    if not _is_bullish(first):
        return None
    if not _is_bearish(third):
        return None
    avg = _avg_body([first, third])
    if avg == 0:
        return None
    if _body(star) > avg * 0.4:
        return None
    first_mid = (first.open + first.close) / 2
    if third.close < first_mid:
        strength = min(1.0, _body(third) / avg) * 0.85
        return PatternMatch("evening_star", "bearish", strength, idx)
    return None


def _detect_three_white_soldiers(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Three white soldiers: 3 consecutive bullish candles with higher closes."""
    if idx < 2:
        return None
    c1, c2, c3 = candles[idx - 2], candles[idx - 1], candles[idx]

    if not all(_is_bullish(c) for c in [c1, c2, c3]):
        return None
    if not (c2.close > c1.close and c3.close > c2.close):
        return None
    if not (c2.open > c1.open and c3.open > c2.open):
        return None
    # Each candle should have small upper wicks
    avg = _avg_body([c1, c2, c3])
    if avg > 0 and all(_upper_wick(c) < _body(c) * 0.5 for c in [c1, c2, c3]):
        return PatternMatch("three_white_soldiers", "bullish", 0.9, idx)
    return None


def _detect_three_black_crows(candles: list[Candle], idx: int) -> PatternMatch | None:
    """Three black crows: 3 consecutive bearish candles with lower closes."""
    if idx < 2:
        return None
    c1, c2, c3 = candles[idx - 2], candles[idx - 1], candles[idx]

    if not all(_is_bearish(c) for c in [c1, c2, c3]):
        return None
    if not (c2.close < c1.close and c3.close < c2.close):
        return None
    if not (c2.open < c1.open and c3.open < c2.open):
        return None
    avg = _avg_body([c1, c2, c3])
    if avg > 0 and all(_lower_wick(c) < _body(c) * 0.5 for c in [c1, c2, c3]):
        return PatternMatch("three_black_crows", "bearish", 0.9, idx)
    return None


# ── Main detection function ─────────────────────────────────────

def detect_patterns(candles: list[Candle], lookback: int = 5) -> list[PatternMatch]:
    """Scan recent candles for all known patterns.

    Args:
        candles: List of finalized Candle objects (oldest first).
        lookback: How many recent candles to scan (default: last 5).

    Returns:
        List of PatternMatch objects found, sorted by strength descending.
    """
    if len(candles) < 2:
        return []

    patterns: list[PatternMatch] = []
    start = max(0, len(candles) - lookback)

    detectors = [
        _detect_hammer,
        _detect_inverted_hammer,
        _detect_shooting_star,
        _detect_doji,
        _detect_spinning_top,
        _detect_bullish_engulfing,
        _detect_bearish_engulfing,
        _detect_morning_star,
        _detect_evening_star,
        _detect_three_white_soldiers,
        _detect_three_black_crows,
    ]

    for idx in range(start, len(candles)):
        for detector in detectors:
            result = detector(candles, idx)
            if result is not None:
                patterns.append(result)

    # Sort by strength descending
    patterns.sort(key=lambda p: p.strength, reverse=True)
    return patterns


# ── Support/Resistance Detection ────────────────────────────────

def detect_support_resistance(
    candles: list[Candle],
    tolerance_pct: float = 0.5,
    min_touches: int = 2,
) -> list[SRLevel]:
    """Detect horizontal support and resistance levels from swing highs/lows.

    Scans for local minima (support) and maxima (resistance) in the candle
    data, then clusters nearby levels.

    Args:
        candles: OHLCV candles (oldest first).
        tolerance_pct: How close prices must be to cluster (% of price).
        min_touches: Minimum touches to qualify as a level.

    Returns:
        List of SRLevel objects.
    """
    if len(candles) < 5:
        return []

    swing_highs: list[tuple[float, int]] = []
    swing_lows: list[tuple[float, int]] = []

    for i in range(2, len(candles) - 2):
        # Swing high: higher high than 2 candles on each side
        if (candles[i].high >= candles[i - 1].high
                and candles[i].high >= candles[i - 2].high
                and candles[i].high >= candles[i + 1].high
                and candles[i].high >= candles[i + 2].high):
            swing_highs.append((candles[i].high, i))

        # Swing low: lower low than 2 candles on each side
        if (candles[i].low <= candles[i - 1].low
                and candles[i].low <= candles[i - 2].low
                and candles[i].low <= candles[i + 1].low
                and candles[i].low <= candles[i + 2].low):
            swing_lows.append((candles[i].low, i))

    levels: list[SRLevel] = []

    # Cluster swing highs into resistance levels
    for cluster_price, touches, last_idx in _cluster_levels(swing_highs, tolerance_pct):
        if touches >= min_touches:
            levels.append(SRLevel(cluster_price, "resistance", touches, last_idx))

    # Cluster swing lows into support levels
    for cluster_price, touches, last_idx in _cluster_levels(swing_lows, tolerance_pct):
        if touches >= min_touches:
            levels.append(SRLevel(cluster_price, "support", touches, last_idx))

    # Sort by price
    levels.sort(key=lambda l: l.price)
    return levels


def _cluster_levels(
    points: list[tuple[float, int]],
    tolerance_pct: float,
) -> list[tuple[float, int, int]]:
    """Cluster nearby price points into levels.

    Returns: [(avg_price, touch_count, last_touch_idx), ...]
    """
    if not points:
        return []

    sorted_pts = sorted(points, key=lambda p: p[0])
    clusters: list[list[tuple[float, int]]] = []
    current_cluster: list[tuple[float, int]] = [sorted_pts[0]]

    for i in range(1, len(sorted_pts)):
        price, idx = sorted_pts[i]
        cluster_avg = sum(p for p, _ in current_cluster) / len(current_cluster)
        if abs(price - cluster_avg) / cluster_avg * 100 <= tolerance_pct:
            current_cluster.append((price, idx))
        else:
            clusters.append(current_cluster)
            current_cluster = [(price, idx)]
    clusters.append(current_cluster)

    result = []
    for cluster in clusters:
        avg_price = sum(p for p, _ in cluster) / len(cluster)
        last_idx = max(idx for _, idx in cluster)
        result.append((avg_price, len(cluster), last_idx))

    return result
