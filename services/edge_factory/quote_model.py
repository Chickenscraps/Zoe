from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import EdgeFactoryConfig

logger = logging.getLogger(__name__)


@dataclass
class Quote:
    """A single BBO (Best Bid/Offer) snapshot."""

    symbol: str
    bid: float
    ask: float
    mid: float
    spread_abs: float
    spread_pct: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class QuoteModel:
    """
    BBO cache with rolling history and staleness detection.

    Wraps exchange client get_best_bid_ask() with:
    - Per-symbol rolling deque of recent quotes
    - Staleness detection (configurable threshold)
    - Average spread calculation for execution policy decisions
    - Avoids redundant API calls within a single tick
    """

    def __init__(
        self,
        exchange_client: Any,
        config: EdgeFactoryConfig,
        max_history: int = 100,
    ):
        self.exchange = exchange_client
        self.config = config
        self._cache: dict[str, deque[Quote]] = {}
        self._max_history = max_history

    async def refresh(self, symbol: str) -> Quote:
        """Fetch fresh BBO from RH, cache it, return Quote."""
        data = await self.exchange.get_best_bid_ask(symbol)
        results = data.get("results", [])

        if not results:
            raise ValueError(f"No BBO data for {symbol}")

        entry = results[0] if isinstance(results, list) else data
        bid = float(entry.get("bid_inclusive_of_sell_spread", entry.get("bid_price", 0)))
        ask = float(entry.get("ask_inclusive_of_buy_spread", entry.get("ask_price", 0)))

        if bid <= 0 or ask <= 0:
            raise ValueError(f"Invalid BBO for {symbol}: bid={bid}, ask={ask}")

        mid = (bid + ask) / 2.0
        spread_abs = ask - bid
        spread_pct = spread_abs / mid if mid > 0 else 0.0

        quote = Quote(
            symbol=symbol,
            bid=bid,
            ask=ask,
            mid=mid,
            spread_abs=spread_abs,
            spread_pct=spread_pct,
        )

        if symbol not in self._cache:
            self._cache[symbol] = deque(maxlen=self._max_history)
        self._cache[symbol].append(quote)

        return quote

    def latest(self, symbol: str) -> Quote | None:
        """Get most recent quote. Returns None if no data or stale."""
        if symbol not in self._cache or not self._cache[symbol]:
            return None
        quote = self._cache[symbol][-1]
        if self.is_stale(symbol):
            return None
        return quote

    def latest_unchecked(self, symbol: str) -> Quote | None:
        """Get most recent quote without staleness check."""
        if symbol not in self._cache or not self._cache[symbol]:
            return None
        return self._cache[symbol][-1]

    def is_stale(self, symbol: str) -> bool:
        """True if last quote older than threshold."""
        if symbol not in self._cache or not self._cache[symbol]:
            return True
        last = self._cache[symbol][-1]
        age = (datetime.now(timezone.utc) - last.timestamp).total_seconds()
        return age > self.config.quote_stale_sec

    def avg_spread_pct(self, symbol: str, window: int = 20) -> float:
        """Rolling average spread from cached history."""
        if symbol not in self._cache or not self._cache[symbol]:
            return 0.0
        quotes = list(self._cache[symbol])[-window:]
        if not quotes:
            return 0.0
        return sum(q.spread_pct for q in quotes) / len(quotes)

    def mid_price(self, symbol: str) -> float:
        """Latest mid, or 0.0 if unavailable."""
        if symbol not in self._cache or not self._cache[symbol]:
            return 0.0
        return self._cache[symbol][-1].mid

    def bid_price(self, symbol: str) -> float:
        """Latest bid, or 0.0 if unavailable."""
        if symbol not in self._cache or not self._cache[symbol]:
            return 0.0
        return self._cache[symbol][-1].bid

    def ask_price(self, symbol: str) -> float:
        """Latest ask, or 0.0 if unavailable."""
        if symbol not in self._cache or not self._cache[symbol]:
            return 0.0
        return self._cache[symbol][-1].ask

    def history_count(self, symbol: str) -> int:
        """Number of cached quotes for a symbol."""
        if symbol not in self._cache:
            return 0
        return len(self._cache[symbol])
