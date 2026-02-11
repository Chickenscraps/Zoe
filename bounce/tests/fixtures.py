"""
Deterministic fixtures for bounce catcher tests.

Provides synthetic OHLCV DataFrames that simulate:
  - Capitulation events (waterfall + recovery wick)
  - Stabilization (higher lows, breakout)
  - Falling knife (continued waterfall, no bounce)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd


def make_capitulation_df(n: int = 60) -> pd.DataFrame:
    """
    Build a 15m candle series with a clear capitulation event at the end.

    Structure (60 bars):
    - Bars 0-44: gentle downtrend (close falls from 100 → ~90)
    - Bar 45: CAPITULATION CANDLE
        - huge range (ATR spike ~3x)
        - big volume (2.5x average)
        - long lower wick (wick ratio ~0.55)
    - Bars 46-59: stabilization (higher lows, slight recovery)
    """
    rng = np.random.RandomState(42)
    t0 = datetime(2025, 6, 1, tzinfo=timezone.utc)

    rows = []
    # Phase 1: gentle downtrend
    for i in range(45):
        base = 100 - i * 0.22
        noise = rng.uniform(-0.3, 0.3)
        close = base + noise
        high = close + rng.uniform(0.3, 1.0)
        low = close - rng.uniform(0.3, 1.0)
        opn = close + rng.uniform(-0.5, 0.5)
        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * i),
            "open": round(opn, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": 1000.0 + rng.uniform(-100, 100),
        })

    # Phase 2: Capitulation candle (bar 45)
    prev_close = rows[-1]["close"]
    cap_open = prev_close - 0.5
    cap_low = prev_close - 8.0       # massive drop
    cap_close = prev_close - 3.0     # recovered significantly
    cap_high = prev_close + 0.5
    cap_volume = 2800.0              # ~2.8x average

    rows.append({
        "timestamp": t0 + timedelta(minutes=15 * 45),
        "open": round(cap_open, 4),
        "high": round(cap_high, 4),
        "low": round(cap_low, 4),
        "close": round(cap_close, 4),
        "volume": cap_volume,
    })

    # Phase 3: Stabilization (higher lows, slight recovery)
    base = cap_close
    for i in range(14):
        # Each bar's low is slightly higher than previous
        base_shift = base + i * 0.15
        noise = rng.uniform(-0.1, 0.1)
        close = base_shift + rng.uniform(0, 0.5) + noise
        high = close + rng.uniform(0.3, 0.8)
        low = base_shift - rng.uniform(0, 0.3) + noise
        opn = close + rng.uniform(-0.3, 0.3)
        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * (46 + i)),
            "open": round(opn, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": 1100 + rng.uniform(-50, 50),
        })

    df = pd.DataFrame(rows)
    df.set_index("timestamp", inplace=True)
    return df


def make_falling_knife_df(n: int = 60) -> pd.DataFrame:
    """
    Build a 15m series with a false capitulation (falling knife).

    Structure:
    - Bars 0-44: downtrend
    - Bar 45: looks like capitulation (big range, volume, wick)
    - Bars 46-59: CONTINUED WATERFALL (lower lows, no stabilization)

    The bot should NOT enter a trade here.
    """
    rng = np.random.RandomState(42)
    t0 = datetime(2025, 6, 1, tzinfo=timezone.utc)

    rows = []
    for i in range(45):
        base = 100 - i * 0.25
        close = base + rng.uniform(-0.3, 0.3)
        high = close + rng.uniform(0.3, 1.0)
        low = close - rng.uniform(0.3, 1.0)
        opn = close + rng.uniform(-0.5, 0.5)
        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * i),
            "open": round(opn, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": 1000 + rng.uniform(-100, 100),
        })

    # False capitulation candle
    prev_close = rows[-1]["close"]
    rows.append({
        "timestamp": t0 + timedelta(minutes=15 * 45),
        "open": round(prev_close - 0.5, 4),
        "high": round(prev_close + 0.3, 4),
        "low": round(prev_close - 7.0, 4),
        "close": round(prev_close - 2.5, 4),
        "volume": 2500.0,
    })

    # Continued waterfall (lower lows — NO stabilization)
    base = prev_close - 2.5
    for i in range(14):
        base -= 0.8  # keeps falling
        close = base + rng.uniform(-0.2, 0.2)
        high = close + rng.uniform(0.2, 0.5)
        low = close - rng.uniform(0.5, 1.5)
        opn = close + rng.uniform(-0.3, 0.3)
        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * (46 + i)),
            "open": round(opn, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": 1200 + rng.uniform(-50, 50),
        })

    df = pd.DataFrame(rows)
    df.set_index("timestamp", inplace=True)
    return df


def make_flat_candles_df(n: int = 30) -> pd.DataFrame:
    """Edge case: nearly flat candles (doji) for wick ratio divide-by-zero."""
    t0 = datetime(2025, 6, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        p = 100.0
        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * i),
            "open": p,
            "high": p + 0.001,
            "low": p - 0.001,
            "close": p,
            "volume": 100.0,
        })
    df = pd.DataFrame(rows)
    df.set_index("timestamp", inplace=True)
    return df
