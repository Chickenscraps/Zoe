"""
Price Cache — in-memory + SQLite-backed BBO cache.

Fixes the broken PaperBroker import by providing the PriceCache class.
Fed by WS ticker callbacks, backed by LocalEventStore.local_ticker_cache.

Usage:
    cache = PriceCache(local_store)
    cache.update("BTC-USD", bid=69000.0, ask=69010.0)
    snap = cache.snapshot("BTC-USD")
    # {"bid": 69000.0, "ask": 69010.0, "mid": 69005.0, "spread_pct": 0.014}
"""
from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from services.local_store import LocalEventStore


class PriceCache:
    """In-memory + SQLite-backed BBO price cache.

    Satisfies the protocol needed by PaperBroker and other components
    that need fast price lookups.
    """

    def __init__(self, local_store: LocalEventStore | None = None) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._store = local_store

    def update(self, symbol: str, bid: float, ask: float) -> None:
        """Update cached BBO for a symbol. Called by WS ticker callback."""
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0
        spread_pct = ((ask - bid) / mid * 100) if mid > 0 else 0.0

        self._cache[symbol] = {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread_pct": spread_pct,
            "ts": time.time(),
        }

        # Write-through to SQLite for persistence across restarts
        if self._store:
            try:
                self._store.update_ticker(symbol, bid, ask)
            except Exception:
                pass  # Non-fatal — in-memory cache is primary

    def snapshot(self, symbol: str) -> dict[str, Any]:
        """Get BBO snapshot for a symbol.

        Priority: in-memory cache → SQLite fallback → zeros.
        """
        if symbol in self._cache:
            return self._cache[symbol]

        # Fallback to SQLite
        if self._store:
            ticker = self._store.get_ticker(symbol)
            if ticker:
                return {
                    "bid": ticker.get("bid", 0),
                    "ask": ticker.get("ask", 0),
                    "mid": ticker.get("mid", 0),
                    "spread_pct": ticker.get("spread_pct", 0),
                    "ts": 0,
                }

        return {"bid": 0, "ask": 0, "mid": 0, "spread_pct": 0, "ts": 0}

    def get_mid(self, symbol: str) -> float:
        """Get mid price for a symbol. Returns 0.0 if unavailable."""
        return self.snapshot(symbol).get("mid", 0.0)

    def has_price(self, symbol: str) -> bool:
        """Check if we have a non-zero price for this symbol."""
        return self.get_mid(symbol) > 0

    def get_all(self) -> dict[str, dict[str, Any]]:
        """Get all cached prices."""
        result = {}
        # Start with SQLite (older)
        if self._store:
            for sym, ticker in self._store.get_all_tickers().items():
                result[sym] = {
                    "bid": ticker.get("bid", 0),
                    "ask": ticker.get("ask", 0),
                    "mid": ticker.get("mid", 0),
                    "spread_pct": ticker.get("spread_pct", 0),
                    "ts": 0,
                }
        # Override with in-memory (fresher)
        result.update(self._cache)
        return result
