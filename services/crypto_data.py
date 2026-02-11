"""
Crypto Data Service — DataFrame wrapper over MarketData for the
trendlines / bounce pipeline.

Provides:
    get_candles(symbol, timeframe, limit) → pd.DataFrame
    get_market_state(symbol)              → Dict with bid/ask/spread/24h stats

All downstream modules (trendlines, bounce) expect a DataFrame with columns:
    timestamp (ms epoch), open, high, low, close, volume
sorted oldest-first.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


class CryptoDataService:
    """Thin orchestration layer between Polygon market data and the analysis pipeline."""

    def __init__(self, market_data=None):
        # Lazy import to avoid circular dependency at module scope
        if market_data is None:
            from market_data import market_data as _md
            self._md = _md
        else:
            self._md = market_data

    # ── Candle Data ──────────────────────────────────────────────────

    def get_candles(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 200,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles and return as a pandas DataFrame.

        Columns: timestamp, open, high, low, close, volume
        Index:   0-based integer (not datetime); timestamp is ms-epoch column.
        Sorted:  oldest → newest (row 0 is oldest).
        """
        bars = self._md.get_crypto_bars(symbol, timeframe, limit)

        if not bars:
            logger.warning("No candle data returned for %s %s", symbol, timeframe)
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(bars)

        # Ensure numeric types
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Drop rows with NaN prices
        df.dropna(subset=["open", "high", "low", "close"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    # ── Indicators ───────────────────────────────────────────────────

    def compute_rsi(self, df: pd.DataFrame, length: int = 14) -> float:
        """Compute current RSI from a candle DataFrame."""
        if df.empty or len(df) < length + 1:
            return 50.0  # neutral default
        try:
            rsi_series = ta.rsi(df["close"], length=length)
            if rsi_series is not None and len(rsi_series) > 0:
                val = rsi_series.iloc[-1]
                if not np.isnan(val):
                    return float(val)
        except Exception as e:
            logger.warning("RSI computation failed: %s", e)
        return 50.0

    # ── Market State (bid/ask/spread/24h range) ──────────────────────

    def get_market_state(self, symbol: str) -> Dict[str, Any]:
        """
        Build a market_state dict compatible with bounce catcher guards.

        Expected keys:
            bid, ask, spread_pct, price,
            open_24h, high_24h, low_24h
        """
        price = self._md.get_crypto_price(symbol)

        # Default state when we can't get detailed data
        state: Dict[str, Any] = {
            "price": price,
            "bid": price,
            "ask": price,
            "spread_pct": 0.0,
            "open_24h": price,
            "high_24h": price,
            "low_24h": price,
        }

        if price <= 0:
            return state

        # Try to get 24h stats from daily bar
        try:
            daily_bars = self._md.get_crypto_bars(symbol, "1d", 2)
            if daily_bars and len(daily_bars) >= 1:
                today = daily_bars[-1]
                state["open_24h"] = today["open"]
                state["high_24h"] = today["high"]
                state["low_24h"] = today["low"]
        except Exception as e:
            logger.debug("Failed to get daily bar for %s: %s", symbol, e)

        return state

    # ── Convenience: build full indicators dict ─────────────────────

    def build_indicators(
        self,
        symbol: str,
        df_15m: pd.DataFrame,
        external_indicators: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Assemble the indicators dict expected by the bounce catcher.

        Merges locally-computed RSI with any external data
        (funding rate, fear & greed, etc.).
        """
        indicators: Dict[str, Any] = {
            "rsi_15m": self.compute_rsi(df_15m, length=14),
        }

        if external_indicators:
            indicators.update(external_indicators)

        return indicators
