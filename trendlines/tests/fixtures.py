"""
Deterministic fixtures for trendlines tests.

These fixtures produce OHLCV DataFrames with known structure so tests
can assert exact pivot locations, trendline parameters, and level zones.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd


def make_uptrend_df(n: int = 100, start_price: float = 100.0, slope: float = 0.5) -> pd.DataFrame:
    """
    Create a clean uptrend with periodic pullbacks.

    Structure:
    - Price rises linearly with small sine-wave pullbacks
    - Creates clear pivot lows along the rising trendline
    - Volume is constant (1000)
    """
    rng = np.random.RandomState(42)  # deterministic noise
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)

    rows = []
    for i in range(n):
        base = start_price + slope * i
        # Sine wave creates regular pullbacks (pivots every ~10 bars)
        wave = 3.0 * np.sin(2 * np.pi * i / 20)
        noise = rng.uniform(-0.3, 0.3)

        close = base + wave + noise
        high = close + rng.uniform(0.5, 2.0)
        low = close - rng.uniform(0.5, 2.0)
        opn = close + rng.uniform(-1, 1)

        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * i),
            "open": round(opn, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": 1000.0,
        })

    df = pd.DataFrame(rows)
    df.set_index("timestamp", inplace=True)
    return df


def make_range_bound_df(n: int = 100, center: float = 50000.0, half_range: float = 500.0) -> pd.DataFrame:
    """
    Create a range-bound (sideways) price series.

    Structure:
    - Price oscillates between center ± half_range
    - Creates clusters of pivots at top and bottom of range
    - Ideal for testing DBSCAN horizontal levels
    """
    rng = np.random.RandomState(42)
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)

    rows = []
    for i in range(n):
        wave = half_range * np.sin(2 * np.pi * i / 30)
        noise = rng.uniform(-50, 50)
        close = center + wave + noise
        high = close + rng.uniform(50, 200)
        low = close - rng.uniform(50, 200)
        opn = close + rng.uniform(-100, 100)

        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * i),
            "open": round(opn, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": 1000.0,
        })

    df = pd.DataFrame(rows)
    df.set_index("timestamp", inplace=True)
    return df


def make_breakout_df() -> pd.DataFrame:
    """
    Create a fixture with a clear breakout from a resistance zone.

    Structure:
    - 50 bars of ranging near 100 (resistance zone)
    - 10 bars pushing above 102 (breakout closes)
    """
    rng = np.random.RandomState(42)
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)

    rows = []
    for i in range(50):
        close = 98 + rng.uniform(-1, 2)
        high = close + rng.uniform(0.5, 1.5)
        low = close - rng.uniform(0.5, 1.5)
        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * i),
            "open": close + rng.uniform(-0.5, 0.5),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": 1000.0,
        })

    for i in range(10):
        close = 103 + rng.uniform(0, 2)
        high = close + rng.uniform(0.5, 2)
        low = close - rng.uniform(0.3, 1)
        rows.append({
            "timestamp": t0 + timedelta(minutes=15 * (50 + i)),
            "open": close - rng.uniform(0, 1),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": 2000.0,
        })

    df = pd.DataFrame(rows)
    df.set_index("timestamp", inplace=True)
    return df
