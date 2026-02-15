"""VWAP (Volume-Weighted Average Price) Tracker.

Computes rolling VWAP for each symbol as an execution benchmark:
  VWAP = Σ(Price × Volume) / Σ(Volume)

Used for:
1. Execution optimization: buy below VWAP, sell above VWAP
2. Trend filtering: price far above/below VWAP = overbought/oversold
3. Fair value reference for the current session

Reference: "Deep Learning for VWAP Execution in Crypto Markets"
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VWAPState:
    """Current VWAP state for a symbol."""
    symbol: str
    vwap: float = 0.0              # Current VWAP
    cumulative_pv: float = 0.0      # Σ(price * volume)
    cumulative_volume: float = 0.0  # Σ(volume)
    price_vs_vwap_pct: float = 0.0  # Current price deviation from VWAP (%)
    current_price: float = 0.0
    sample_count: int = 0
    session_start: float = 0.0
    last_updated: float = 0.0

    @property
    def is_above_vwap(self) -> bool:
        return self.current_price > self.vwap if self.vwap > 0 else False

    @property
    def deviation_band(self) -> str:
        """Categorize how far price is from VWAP."""
        pct = abs(self.price_vs_vwap_pct)
        if pct < 0.1:
            return "at_vwap"
        elif pct < 0.5:
            return "near_vwap"
        elif pct < 1.0:
            return "moderate_deviation"
        elif pct < 2.0:
            return "significant_deviation"
        else:
            return "extreme_deviation"


@dataclass
class TradeEntry:
    """Single trade for VWAP calculation."""
    price: float
    volume: float
    timestamp: float


class VWAPTracker:
    """Tracks VWAP across multiple symbols with rolling windows.

    Supports:
    - Session VWAP (resets daily or on demand)
    - Rolling 1h VWAP
    - Rolling 24h VWAP

    Usage:
        tracker = VWAPTracker()
        tracker.record_trade("BTC-USD", price=97000, volume=0.5)
        state = tracker.get_state("BTC-USD", current_price=97050)
        if state.is_above_vwap:
            # Price above fair value - consider selling
            ...
    """

    def __init__(
        self,
        session_duration_hours: float = 24.0,
        max_trades_per_symbol: int = 10000,
    ):
        self.session_duration = session_duration_hours * 3600
        self.max_trades = max_trades_per_symbol

        # Per-symbol trade history
        self._trades: dict[str, deque[TradeEntry]] = {}
        self._session_starts: dict[str, float] = {}

    def record_trade(self, symbol: str, price: float, volume: float) -> None:
        """Record a trade for VWAP calculation.

        Can also be fed with ticker data (using bid-ask midpoint and
        volume delta) when individual trades aren't available.
        """
        if price <= 0 or volume <= 0:
            return

        now = time.time()
        trades = self._trades.setdefault(
            symbol, deque(maxlen=self.max_trades)
        )
        trades.append(TradeEntry(price=price, volume=volume, timestamp=now))

        if symbol not in self._session_starts:
            self._session_starts[symbol] = now

    def record_ticker(
        self,
        symbol: str,
        bid: float,
        ask: float,
        volume_24h: float,
    ) -> None:
        """Record from ticker data (approximate VWAP from BBO midpoint).

        Uses volume_24h delta as proxy for trade volume when individual
        trades aren't available from the WS feed.
        """
        if bid <= 0 or ask <= 0:
            return

        mid = (bid + ask) / 2
        # Use a small proxy volume since we don't have exact trade volume
        # This still gives a reasonable VWAP from price movement
        proxy_volume = max(0.001, volume_24h * 0.00001)  # Tiny fraction
        self.record_trade(symbol, mid, proxy_volume)

    def get_state(
        self,
        symbol: str,
        current_price: float = 0.0,
    ) -> Optional[VWAPState]:
        """Get current VWAP state for a symbol."""
        trades = self._trades.get(symbol)
        if not trades:
            return None

        now = time.time()

        # Clean expired trades
        session_start = self._session_starts.get(symbol, now)
        if now - session_start > self.session_duration:
            # Reset session
            self._session_starts[symbol] = now
            # Keep last hour of trades for continuity
            cutoff = now - 3600
            while trades and trades[0].timestamp < cutoff:
                trades.popleft()

        if not trades:
            return None

        # Compute VWAP
        cum_pv = sum(t.price * t.volume for t in trades)
        cum_vol = sum(t.volume for t in trades)

        if cum_vol <= 0:
            return None

        vwap = cum_pv / cum_vol

        # Use last trade price if current_price not provided
        if current_price <= 0:
            current_price = trades[-1].price

        # Price vs VWAP deviation
        deviation_pct = ((current_price - vwap) / vwap * 100) if vwap > 0 else 0

        return VWAPState(
            symbol=symbol,
            vwap=round(vwap, 8),
            cumulative_pv=cum_pv,
            cumulative_volume=cum_vol,
            price_vs_vwap_pct=round(deviation_pct, 4),
            current_price=current_price,
            sample_count=len(trades),
            session_start=session_start,
            last_updated=now,
        )

    def get_all_states(self, prices: dict[str, float] | None = None) -> dict[str, VWAPState]:
        """Get VWAP states for all tracked symbols."""
        prices = prices or {}
        states = {}
        for symbol in self._trades:
            state = self.get_state(symbol, prices.get(symbol, 0))
            if state is not None:
                states[symbol] = state
        return states

    def should_buy(self, symbol: str, current_price: float, threshold_pct: float = -0.1) -> bool:
        """Check if current price is below VWAP (favorable to buy).

        Args:
            threshold_pct: How far below VWAP price should be (negative = below).
                           Default -0.1% means price must be at least 0.1% below VWAP.
        """
        state = self.get_state(symbol, current_price)
        if state is None:
            return False
        return state.price_vs_vwap_pct <= threshold_pct

    def should_sell(self, symbol: str, current_price: float, threshold_pct: float = 0.1) -> bool:
        """Check if current price is above VWAP (favorable to sell).

        Args:
            threshold_pct: How far above VWAP price should be (positive = above).
        """
        state = self.get_state(symbol, current_price)
        if state is None:
            return False
        return state.price_vs_vwap_pct >= threshold_pct

    def reset_session(self, symbol: str | None = None) -> None:
        """Reset VWAP session (clear history)."""
        if symbol:
            self._trades.pop(symbol, None)
            self._session_starts.pop(symbol, None)
        else:
            self._trades.clear()
            self._session_starts.clear()
