"""
Pivot detection — the atomic units of market structure.

Implements vectorized fractal detection for both wick and body pivots,
with ATR-based significance filtering and confirmation-lag handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class Pivot:
    """A confirmed structural pivot point."""
    timestamp: datetime
    price: float
    type: str          # 'high' | 'low'
    source: str        # 'wick' | 'body'
    atr_snapshot: Optional[float] = None
    idx: Optional[int] = None  # original df index for back-ref


def detect_pivots_vectorized(
    df: pd.DataFrame,
    k: int = 3,
    sources: Optional[List[str]] = None,
) -> List[Pivot]:
    """
    Detect pivot highs and lows using a rolling-window fractal method.

    A pivot high at index *i* requires that ``high[i]`` is the max of the
    window ``[i-k, i+k]``.  Symmetrically for pivot lows.

    Parameters
    ----------
    df : DataFrame
        Must contain columns: open, high, low, close.  Index should be a
        DatetimeIndex or contain a 'timestamp' column.
    k : int
        Half-window size.  ``k=3`` → 7-bar window (classic Bill Williams).
    sources : list[str], optional
        Which pivot sources to compute.  Default ``["wick", "body"]``.

    Returns
    -------
    list[Pivot]
        Confirmed pivots sorted by timestamp.  *Confirmation lag* means
        pivots are only emitted for bars where we have ``k`` future bars
        available (i.e. everything except the last ``k`` bars).
    """
    if sources is None:
        sources = ["wick", "body"]

    window = 2 * k + 1
    pivots: List[Pivot] = []
    n = len(df)

    if n < window:
        return pivots

    timestamps = _resolve_timestamps(df)

    for src in sources:
        if src == "wick":
            high_series = df["high"].values
            low_series = df["low"].values
        else:  # body
            high_series = np.maximum(df["open"].values, df["close"].values)
            low_series = np.minimum(df["open"].values, df["close"].values)

        # Vectorised rolling max/min (centre-aligned)
        high_pd = pd.Series(high_series)
        low_pd = pd.Series(low_series)

        rolling_max = high_pd.rolling(window=window, center=True).max().values
        rolling_min = low_pd.rolling(window=window, center=True).min().values

        # Confirmed range: we need k bars to the right to confirm
        confirm_end = n - k

        for i in range(k, confirm_end):
            if high_series[i] == rolling_max[i] and not np.isnan(rolling_max[i]):
                pivots.append(Pivot(
                    timestamp=timestamps[i],
                    price=float(high_series[i]),
                    type="high",
                    source=src,
                    idx=i,
                ))
            if low_series[i] == rolling_min[i] and not np.isnan(rolling_min[i]):
                pivots.append(Pivot(
                    timestamp=timestamps[i],
                    price=float(low_series[i]),
                    type="low",
                    source=src,
                    idx=i,
                ))

    # Deduplicate pivots at the exact same (timestamp, type, source)
    seen = set()
    unique: List[Pivot] = []
    for p in pivots:
        key = (p.timestamp, p.type, p.source)
        if key not in seen:
            seen.add(key)
            unique.append(p)

    unique.sort(key=lambda p: p.timestamp)
    return unique


def filter_pivots_by_atr(
    pivots: List[Pivot],
    df: pd.DataFrame,
    atr_len: int = 14,
    atr_pivot_mult: float = 0.75,
) -> List[Pivot]:
    """
    Remove pivots whose price excursion is smaller than
    ``atr_pivot_mult * ATR``.  This filters out "noise pivots" during
    low-volatility chop (e.g. weekend drift).

    Also populates ``atr_snapshot`` on each surviving pivot.
    """
    if len(df) < atr_len + 1 or not pivots:
        return pivots

    # Compute ATR (Wilder True Range → simple SMA for speed)
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    tr = np.empty(len(df))
    tr[0] = high[0] - low[0]
    for i in range(1, len(df)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    atr_series = pd.Series(tr).rolling(window=atr_len).mean().values

    filtered: List[Pivot] = []
    for p in pivots:
        idx = p.idx
        if idx is None or idx < atr_len:
            # Can't compute ATR for this bar — keep it but mark None
            filtered.append(p)
            continue
        atr_val = atr_series[idx]
        if np.isnan(atr_val) or atr_val <= 0:
            filtered.append(p)
            continue

        p.atr_snapshot = float(atr_val)

        # For a pivot high, excursion = high - close of that bar
        # For a pivot low,  excursion = close - low of that bar
        if p.source == "wick":
            excursion = abs(high[idx] - low[idx])
        else:
            body_top = max(df["open"].values[idx], close[idx])
            body_bot = min(df["open"].values[idx], close[idx])
            excursion = body_top - body_bot

        if excursion >= atr_pivot_mult * atr_val:
            filtered.append(p)

    return filtered


def compute_atr(df: pd.DataFrame, length: int = 14) -> np.ndarray:
    """Return an ATR series (same length as df, NaN-padded at front)."""
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    tr = np.empty(len(df))
    tr[0] = high[0] - low[0]
    for i in range(1, len(df)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    return pd.Series(tr).rolling(window=length).mean().values


# ── helpers ──────────────────────────────────────────────────────────────

def _resolve_timestamps(df: pd.DataFrame):
    """Extract a numpy array of timestamps from a DataFrame."""
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index.to_pydatetime()
    if "timestamp" in df.columns:
        ts = df["timestamp"]
        if pd.api.types.is_datetime64_any_dtype(ts):
            return ts.dt.to_pydatetime()
        # Try epoch-millis (Polygon convention)
        return pd.to_datetime(ts, unit="ms", utc=True).dt.to_pydatetime()
    raise ValueError("DataFrame must have a DatetimeIndex or 'timestamp' column")
