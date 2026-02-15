"""Order Flow Imbalance (OFI) Tracker.

Implements the OFI signal from microstructure research:
  OFI = (bid pressure changes) - (ask pressure changes)

A positive OFI suggests bullish pressure (more demand arriving),
negative OFI suggests bearish pressure (more supply arriving).

Aggregated over 1s and 5s windows for short-term price prediction.

Reference: "Order Flow Imbalance - A High Frequency Trading Signal"
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BBOState:
    """Best Bid/Offer state for OFI calculation."""
    bid_price: float = 0.0
    bid_size: float = 0.0
    ask_price: float = 0.0
    ask_size: float = 0.0
    timestamp: float = 0.0


@dataclass
class OFISignal:
    """Computed OFI signal for a symbol."""
    symbol: str
    ofi_1s: float = 0.0        # 1-second aggregated OFI
    ofi_5s: float = 0.0        # 5-second aggregated OFI
    ofi_30s: float = 0.0       # 30-second aggregated OFI
    direction: str = "neutral"  # "bullish", "bearish", "neutral"
    strength: float = 0.0       # Normalized strength [0, 1]
    timestamp: float = 0.0


@dataclass
class OFIEntry:
    """Single OFI measurement."""
    delta: float
    timestamp: float


class OFITracker:
    """Tracks Order Flow Imbalance across multiple symbols.

    For each symbol, maintains:
    - Previous BBO state
    - Rolling window of OFI deltas
    - Computed 1s, 5s, 30s aggregated signals

    Usage:
        tracker = OFITracker()
        tracker.update("BTC-USD", bid=97000, bid_size=1.5, ask=97010, ask_size=2.0)
        signal = tracker.get_signal("BTC-USD")
        if signal and signal.direction == "bullish" and signal.strength > 0.7:
            # Strong buy pressure detected
            ...
    """

    def __init__(
        self,
        window_1s: float = 1.0,
        window_5s: float = 5.0,
        window_30s: float = 30.0,
        strength_threshold: float = 0.3,
        max_history: int = 600,  # ~10 minutes at 1 update/sec
    ):
        self.window_1s = window_1s
        self.window_5s = window_5s
        self.window_30s = window_30s
        self.strength_threshold = strength_threshold
        self.max_history = max_history

        # Per-symbol state
        self._prev_bbo: dict[str, BBOState] = {}
        self._ofi_history: dict[str, deque[OFIEntry]] = {}

    def update(
        self,
        symbol: str,
        bid: float,
        bid_size: float,
        ask: float,
        ask_size: float,
    ) -> Optional[OFISignal]:
        """Update BBO for a symbol and compute OFI delta.

        Returns the current OFI signal if enough data exists.
        """
        now = time.time()
        prev = self._prev_bbo.get(symbol)

        if prev is None or prev.timestamp == 0:
            # First observation — just store state
            self._prev_bbo[symbol] = BBOState(
                bid_price=bid, bid_size=bid_size,
                ask_price=ask, ask_size=ask_size,
                timestamp=now,
            )
            return None

        # Compute OFI delta using the four-component formula
        delta = self._compute_ofi_delta(prev, bid, bid_size, ask, ask_size)

        # Store delta
        history = self._ofi_history.setdefault(symbol, deque(maxlen=self.max_history))
        history.append(OFIEntry(delta=delta, timestamp=now))

        # Update previous state
        self._prev_bbo[symbol] = BBOState(
            bid_price=bid, bid_size=bid_size,
            ask_price=ask, ask_size=ask_size,
            timestamp=now,
        )

        # Compute aggregated signal
        return self._compute_signal(symbol, now)

    def get_signal(self, symbol: str) -> Optional[OFISignal]:
        """Get the current OFI signal for a symbol without updating."""
        if symbol not in self._ofi_history:
            return None
        return self._compute_signal(symbol, time.time())

    def get_all_signals(self) -> dict[str, OFISignal]:
        """Get all current OFI signals."""
        now = time.time()
        signals = {}
        for symbol in self._ofi_history:
            sig = self._compute_signal(symbol, now)
            if sig is not None:
                signals[symbol] = sig
        return signals

    @staticmethod
    def _compute_ofi_delta(
        prev: BBOState,
        bid: float, bid_size: float,
        ask: float, ask_size: float,
    ) -> float:
        """Compute the OFI delta between two BBO states.

        OFI = (demand_increase - demand_decrease) - (supply_increase - supply_decrease)

        Components:
        1. bid price rises or bid size increases → demand increase
        2. bid price falls or bid size decreases → demand decrease
        3. ask price falls or ask size increases → supply increase
        4. ask price rises or ask size decreases → supply decrease
        """
        # Demand side (bid)
        if bid > prev.bid_price:
            demand_delta = bid_size  # New higher bid = fresh demand
        elif bid == prev.bid_price:
            demand_delta = bid_size - prev.bid_size  # Size change at same level
        else:
            demand_delta = -prev.bid_size  # Bid dropped = demand withdrawn

        # Supply side (ask)
        if ask < prev.ask_price:
            supply_delta = ask_size  # New lower ask = fresh supply
        elif ask == prev.ask_price:
            supply_delta = ask_size - prev.ask_size  # Size change at same level
        else:
            supply_delta = -prev.ask_size  # Ask rose = supply withdrawn

        # OFI = demand pressure - supply pressure
        return demand_delta - supply_delta

    def _compute_signal(self, symbol: str, now: float) -> Optional[OFISignal]:
        """Compute aggregated OFI signal from history."""
        history = self._ofi_history.get(symbol)
        if not history or len(history) < 1:
            return None

        # Aggregate over windows
        ofi_1s = sum(
            e.delta for e in history if now - e.timestamp <= self.window_1s
        )
        ofi_5s = sum(
            e.delta for e in history if now - e.timestamp <= self.window_5s
        )
        ofi_30s = sum(
            e.delta for e in history if now - e.timestamp <= self.window_30s
        )

        # Determine direction and strength from 5s window
        if abs(ofi_5s) < self.strength_threshold:
            direction = "neutral"
            strength = 0.0
        elif ofi_5s > 0:
            direction = "bullish"
            strength = min(1.0, ofi_5s / (self.strength_threshold * 10))
        else:
            direction = "bearish"
            strength = min(1.0, abs(ofi_5s) / (self.strength_threshold * 10))

        return OFISignal(
            symbol=symbol,
            ofi_1s=round(ofi_1s, 4),
            ofi_5s=round(ofi_5s, 4),
            ofi_30s=round(ofi_30s, 4),
            direction=direction,
            strength=round(strength, 4),
            timestamp=now,
        )

    def cleanup(self, max_age_seconds: float = 120) -> int:
        """Remove stale entries older than max_age."""
        cutoff = time.time() - max_age_seconds
        removed = 0
        for symbol in list(self._ofi_history.keys()):
            history = self._ofi_history[symbol]
            before = len(history)
            while history and history[0].timestamp < cutoff:
                history.popleft()
            removed += before - len(history)
            if not history:
                del self._ofi_history[symbol]
                self._prev_bbo.pop(symbol, None)
        return removed
