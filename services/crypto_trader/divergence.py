"""Divergence detection between price action and oscillators.

Detects four divergence types that signal trend reversals or continuations:

Regular (classic) divergence — reversal signals:
  - Regular Bullish: price lower low + indicator higher low → trend reversal up
  - Regular Bearish: price higher high + indicator lower high → trend reversal down

Hidden divergence — continuation signals:
  - Hidden Bullish: price higher low + indicator lower low → trend continues up
  - Hidden Bearish: price lower high + indicator higher high → trend continues down

Research statistics:
  - Regular divergence: ~72% reversal accuracy
  - Hidden divergence: ~65% continuation accuracy
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Divergence:
    """A detected divergence between price and an oscillator."""

    type: str         # "regular_bullish" | "regular_bearish" | "hidden_bullish" | "hidden_bearish"
    strength: float   # 0.0-1.0 based on clarity and magnitude
    indicator: str    # "rsi" or "macd"
    price_pivots: tuple[int, int]      # indices of the two pivots in the price series
    indicator_pivots: tuple[int, int]  # indices of the two pivots in the indicator series

    @property
    def is_reversal(self) -> bool:
        return self.type.startswith("regular")

    @property
    def is_bullish(self) -> bool:
        return "bullish" in self.type

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "strength": round(self.strength, 3),
            "indicator": self.indicator,
            "is_reversal": self.is_reversal,
            "is_bullish": self.is_bullish,
        }


# ── Pivot detection ────────────────────────────────────────────

def _find_swing_pivots(
    values: list[float], window: int = 5,
) -> dict[str, list[tuple[int, float]]]:
    """Find local swing highs and lows in a value series.

    A swing high at index i means values[i] is the highest in
    [i-window, i+window].  Similarly for swing lows.

    Returns dict with "highs" and "lows" as lists of (index, value).
    """
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []

    if len(values) < 2 * window + 1:
        return {"highs": highs, "lows": lows}

    for i in range(window, len(values) - window):
        left = values[i - window : i]
        right = values[i + 1 : i + window + 1]
        val = values[i]

        if all(val > v for v in left) and all(val > v for v in right):
            highs.append((i, val))
        if all(val < v for v in left) and all(val < v for v in right):
            lows.append((i, val))

    return {"highs": highs, "lows": lows}


def _find_nearest(
    pivots: list[tuple[int, float]], target_idx: int, max_distance: int = 8,
) -> tuple[int, float] | None:
    """Find pivot nearest to target_idx within max_distance bars."""
    best = None
    best_dist = max_distance + 1
    for idx, val in pivots:
        d = abs(idx - target_idx)
        if d <= max_distance and d < best_dist:
            best = (idx, val)
            best_dist = d
    return best


# ── Divergence detection ────────────────────────────────────────

def _detect_divergences(
    closes: list[float],
    indicator_values: list[float],
    indicator_name: str,
    pivot_window: int = 5,
    max_pivot_distance: int = 8,
) -> list[Divergence]:
    """Core divergence detection between price closes and an indicator.

    Compares the last two swing pivots in both price and indicator to
    identify regular and hidden divergences.
    """
    n = len(closes)
    if n < 20 or len(indicator_values) != n:
        return []

    price_pivots = _find_swing_pivots(closes, pivot_window)
    ind_pivots = _find_swing_pivots(indicator_values, pivot_window)

    divergences: list[Divergence] = []

    # ── Check lows (bullish divergences) ──
    p_lows = price_pivots["lows"]
    i_lows = ind_pivots["lows"]

    for j in range(1, len(p_lows)):
        p_idx1, p_val1 = p_lows[j - 1]
        p_idx2, p_val2 = p_lows[j]

        # Find corresponding indicator lows
        i1 = _find_nearest(i_lows, p_idx1, max_pivot_distance)
        i2 = _find_nearest(i_lows, p_idx2, max_pivot_distance)
        if i1 is None or i2 is None:
            continue

        # Regular Bullish: price lower low + indicator higher low
        if p_val2 < p_val1 and i2[1] > i1[1]:
            price_drop = (p_val1 - p_val2) / p_val1 if p_val1 else 0
            ind_rise = (i2[1] - i1[1]) / max(abs(i1[1]), 1)
            strength = min(1.0, (price_drop + ind_rise) * 3)
            divergences.append(Divergence(
                type="regular_bullish",
                strength=strength,
                indicator=indicator_name,
                price_pivots=(p_idx1, p_idx2),
                indicator_pivots=(i1[0], i2[0]),
            ))

        # Hidden Bullish: price higher low + indicator lower low
        elif p_val2 > p_val1 and i2[1] < i1[1]:
            strength = min(1.0, abs(i1[1] - i2[1]) / max(abs(i1[1]), 1) * 5)
            divergences.append(Divergence(
                type="hidden_bullish",
                strength=strength,
                indicator=indicator_name,
                price_pivots=(p_idx1, p_idx2),
                indicator_pivots=(i1[0], i2[0]),
            ))

    # ── Check highs (bearish divergences) ──
    p_highs = price_pivots["highs"]
    i_highs = ind_pivots["highs"]

    for j in range(1, len(p_highs)):
        p_idx1, p_val1 = p_highs[j - 1]
        p_idx2, p_val2 = p_highs[j]

        i1 = _find_nearest(i_highs, p_idx1, max_pivot_distance)
        i2 = _find_nearest(i_highs, p_idx2, max_pivot_distance)
        if i1 is None or i2 is None:
            continue

        # Regular Bearish: price higher high + indicator lower high
        if p_val2 > p_val1 and i2[1] < i1[1]:
            price_rise = (p_val2 - p_val1) / p_val1 if p_val1 else 0
            ind_drop = (i1[1] - i2[1]) / max(abs(i1[1]), 1)
            strength = min(1.0, (price_rise + ind_drop) * 3)
            divergences.append(Divergence(
                type="regular_bearish",
                strength=strength,
                indicator=indicator_name,
                price_pivots=(p_idx1, p_idx2),
                indicator_pivots=(i1[0], i2[0]),
            ))

        # Hidden Bearish: price lower high + indicator higher high
        elif p_val2 < p_val1 and i2[1] > i1[1]:
            strength = min(1.0, abs(i2[1] - i1[1]) / max(abs(i1[1]), 1) * 5)
            divergences.append(Divergence(
                type="hidden_bearish",
                strength=strength,
                indicator=indicator_name,
                price_pivots=(p_idx1, p_idx2),
                indicator_pivots=(i1[0], i2[0]),
            ))

    return divergences


# ── Public API ──────────────────────────────────────────────────

def detect_rsi_divergence(
    closes: list[float], rsi_values: list[float], pivot_window: int = 5,
) -> list[Divergence]:
    """Detect divergences between price and RSI.

    Args:
        closes: List of close prices (same length as rsi_values).
        rsi_values: RSI values aligned to closes.
        pivot_window: Number of bars on each side to confirm a swing pivot.
    """
    return _detect_divergences(closes, rsi_values, "rsi", pivot_window)


def detect_macd_divergence(
    closes: list[float], macd_histograms: list[float], pivot_window: int = 5,
) -> list[Divergence]:
    """Detect divergences between price and MACD histogram.

    Args:
        closes: List of close prices (same length as macd_histograms).
        macd_histograms: MACD histogram values aligned to closes.
        pivot_window: Number of bars on each side to confirm a swing pivot.
    """
    return _detect_divergences(closes, macd_histograms, "macd", pivot_window)
