"""
Phase 1 — Capitulation detection.

Scans 15-minute candles for "waterfall" signatures characterised by:
  1. True Range >= atr_mult * ATR  (price expansion outlier)
  2. Volume >= vol_mult * volume MA  (participation spike)
  3. Lower wick ratio >= lower_wick_min  (absorption / recovery)

All three conditions must be satisfied simultaneously.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd


def calculate_wick_ratio(
    open_p: float, high: float, low: float, close: float
) -> float:
    """
    Compute the lower-wick ratio of a candle.

    lower_wick_ratio = (min(open, close) - low) / (high - low)

    Returns 0.0 for flat/invalid candles (divide-by-zero safe).
    """
    total_range = high - low
    if total_range <= 0:
        return 0.0
    body_min = min(open_p, close)
    lower_wick = body_min - low
    if lower_wick < 0:
        return 0.0
    return lower_wick / total_range


def detect_capitulation_event(
    df: pd.DataFrame,
    atr_len: int = 14,
    vol_ma_len: int = 20,
    atr_mult: float = 2.5,
    vol_mult: float = 2.0,
    lower_wick_min: float = 0.45,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Evaluate the **latest candle** in *df* for a capitulation signature.

    Parameters
    ----------
    df : DataFrame
        OHLCV candles (oldest-first).  Must have columns:
        open, high, low, close, volume.  Length >= atr_len + 2.

    Returns
    -------
    (is_capitulation, metrics)
        ``is_capitulation`` is True only when all 3 conditions fire.
        ``metrics`` dict always returned for audit/scoring.
    """
    n = len(df)
    empty_metrics: Dict[str, Any] = {
        "tr": 0, "atr": 0, "vol": 0, "vol_ma": 0,
        "wick_ratio": 0.0,
        "atr_satisfied": False, "vol_satisfied": False, "wick_satisfied": False,
    }

    if n < max(atr_len, vol_ma_len) + 2:
        return False, empty_metrics

    candle = df.iloc[-1]
    prev_close = float(df.iloc[-2]["close"])

    # True range (Wilder)
    tr = max(
        float(candle["high"]) - float(candle["low"]),
        abs(float(candle["high"]) - prev_close),
        abs(float(candle["low"]) - prev_close),
    )

    # ATR (simple rolling mean of true range) — use *previous* bar's ATR
    # to avoid look-ahead bias
    highs = df["high"].values.astype(float)
    lows = df["low"].values.astype(float)
    closes = df["close"].values.astype(float)

    trs = np.empty(n)
    trs[0] = highs[0] - lows[0]
    for i in range(1, n):
        trs[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    atr_series = pd.Series(trs).rolling(window=atr_len).mean().values
    # Use the ATR as-of the *previous* bar
    atr = float(atr_series[-2]) if not np.isnan(atr_series[-2]) else 0.0

    # Volume MA (previous bar)
    vol_ma_series = pd.Series(df["volume"].values.astype(float)).rolling(window=vol_ma_len).mean().values
    vol_ma = float(vol_ma_series[-2]) if not np.isnan(vol_ma_series[-2]) else 0.0

    vol = float(candle["volume"])

    # Conditions
    atr_satisfied = atr > 0 and tr >= atr_mult * atr
    vol_satisfied = vol_ma > 0 and vol >= vol_mult * vol_ma

    wick_ratio = calculate_wick_ratio(
        float(candle["open"]),
        float(candle["high"]),
        float(candle["low"]),
        float(candle["close"]),
    )
    wick_satisfied = wick_ratio >= lower_wick_min

    metrics = {
        "tr": round(tr, 6),
        "atr": round(atr, 6),
        "vol": vol,
        "vol_ma": round(vol_ma, 6),
        "wick_ratio": round(wick_ratio, 6),
        "atr_satisfied": atr_satisfied,
        "vol_satisfied": vol_satisfied,
        "wick_satisfied": wick_satisfied,
        "candle_ts": str(candle.name) if hasattr(candle, "name") else None,
    }

    is_capitulation = atr_satisfied and vol_satisfied and wick_satisfied
    return is_capitulation, metrics
