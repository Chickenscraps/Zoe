"""
Data loaders for backtesting.

Supports:
  1. CSV files (CryptoDataDownload format, Binance, generic OHLCV)
  2. Polygon.io live fetch (via existing market_data module)
  3. Synthetic data generation (for smoke tests)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_csv_candles(
    filepath: str,
    symbol: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load OHLCV candles from a CSV file.

    Handles common formats:
      - CryptoDataDownload: date, symbol, open, high, low, close, volume_btc, volume_usd
      - Binance: open_time, open, high, low, close, volume, close_time, ...
      - Generic: timestamp/date, open, high, low, close, volume

    Returns DataFrame with DatetimeIndex and columns: open, high, low, close, volume.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    df = pd.read_csv(filepath)

    # Normalize column names (lowercase, strip whitespace)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Detect date column
    date_col = None
    for candidate in ["timestamp", "date", "datetime", "time", "open_time", "unix"]:
        if candidate in df.columns:
            date_col = candidate
            break

    if date_col is None:
        raise ValueError(f"No date/timestamp column found. Columns: {list(df.columns)}")

    # Parse dates
    if df[date_col].dtype == "int64" or df[date_col].dtype == "float64":
        # Unix timestamp (seconds or milliseconds)
        vals = df[date_col].astype(float)
        if vals.iloc[0] > 1e12:  # milliseconds
            df.index = pd.to_datetime(vals, unit="ms", utc=True)
        else:
            df.index = pd.to_datetime(vals, unit="s", utc=True)
    else:
        df.index = pd.to_datetime(df[date_col], utc=True)

    df.index.name = "timestamp"

    # Rename columns to standard OHLCV
    rename_map = {}
    for target, candidates in {
        "open": ["open"],
        "high": ["high"],
        "low": ["low"],
        "close": ["close"],
        "volume": ["volume", "volume_usd", "volume_btc", "vol", "quote_volume"],
    }.items():
        for c in candidates:
            if c in df.columns and target not in df.columns:
                rename_map[c] = target
                break

    if rename_map:
        df = df.rename(columns=rename_map)

    # Filter by symbol if applicable
    if symbol and "symbol" in df.columns:
        df = df[df["symbol"].str.contains(symbol.replace("-", ""), case=False)]

    # Keep only OHLCV
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns after normalization: {missing}")

    df = df[required].copy()
    df = df.astype(float)
    df = df.sort_index()
    df = df.dropna()

    logger.info(
        "Loaded %d candles from %s (%s to %s)",
        len(df),
        filepath,
        df.index[0],
        df.index[-1],
    )
    return df


def fetch_polygon_candles(
    symbol: str = "BTC-USD",
    timeframe: str = "15m",
    days: int = 90,
) -> pd.DataFrame:
    """
    Fetch historical candles from Polygon.io using the existing market_data module.

    Returns DataFrame with DatetimeIndex and columns: open, high, low, close, volume.
    """
    from market_data import market_data

    bars = market_data.get_crypto_bars(symbol, timeframe, limit=days * 96)  # ~96 15m candles/day
    if not bars:
        raise RuntimeError(f"No bars returned from Polygon for {symbol}/{timeframe}")

    df = pd.DataFrame(bars)
    df.index = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.index.name = "timestamp"
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df.sort_index()

    logger.info(
        "Fetched %d candles from Polygon for %s/%s (%s to %s)",
        len(df),
        symbol,
        timeframe,
        df.index[0],
        df.index[-1],
    )
    return df


def generate_synthetic_candles(
    n: int = 2000,
    start_price: float = 50000.0,
    volatility: float = 0.015,
    trend: float = 0.0001,
    include_capitulations: int = 5,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data for smoke-testing the backtest engine.

    Includes configurable number of capitulation events (sharp drops with
    volume spikes and lower-wick recovery).

    Parameters
    ----------
    n : int
        Number of candles to generate.
    start_price : float
        Starting price.
    volatility : float
        Per-candle log-return standard deviation.
    trend : float
        Per-candle drift.
    include_capitulations : int
        Number of capitulation-like events to inject.
    seed : int
        Random seed for reproducibility.
    """
    rng = np.random.RandomState(seed)

    timestamps = pd.date_range(
        start="2024-01-01",
        periods=n,
        freq="15min",
        tz="UTC",
    )

    closes = np.zeros(n)
    opens = np.zeros(n)
    highs = np.zeros(n)
    lows = np.zeros(n)
    volumes = np.zeros(n)

    price = start_price

    # Random capitulation injection points
    cap_indices = sorted(rng.choice(range(100, n - 100), size=include_capitulations, replace=False))

    for i in range(n):
        log_ret = rng.normal(trend, volatility)
        base_volume = rng.exponential(100) + 50

        open_price = price
        close_price = price * np.exp(log_ret)

        # Inject capitulation
        if i in cap_indices:
            # Sharp drop with recovery wick
            drop_pct = rng.uniform(0.03, 0.06)
            candle_low = open_price * (1 - drop_pct)
            # Recover 50-70% of the drop (lower wick)
            recovery = rng.uniform(0.5, 0.7)
            close_price = candle_low + (open_price - candle_low) * recovery
            high_price = open_price * (1 + rng.uniform(0, 0.005))
            base_volume *= rng.uniform(3, 6)  # Volume spike
        else:
            candle_range = abs(close_price - open_price) * rng.uniform(0.5, 2.0)
            if close_price >= open_price:
                high_price = close_price + candle_range * rng.uniform(0, 0.5)
                candle_low = open_price - candle_range * rng.uniform(0, 0.5)
            else:
                high_price = open_price + candle_range * rng.uniform(0, 0.5)
                candle_low = close_price - candle_range * rng.uniform(0, 0.5)

        opens[i] = open_price
        highs[i] = max(open_price, close_price, high_price)
        lows[i] = min(open_price, close_price, candle_low)
        closes[i] = close_price
        volumes[i] = base_volume

        price = close_price

    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        },
        index=timestamps,
    )
    df.index.name = "timestamp"

    logger.info(
        "Generated %d synthetic candles (start=$%.2f, end=$%.2f, %d capitulations)",
        n,
        start_price,
        closes[-1],
        include_capitulations,
    )
    return df
