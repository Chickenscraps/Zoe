from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from ..config import EdgeFactoryConfig
from .base import BaseIngestor

logger = logging.getLogger(__name__)

# Symbol -> Google Trends search keyword mapping
SYMBOL_TO_KEYWORD: dict[str, str] = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "DOGE-USD": "Dogecoin",
    "SOL-USD": "Solana",
    "ADA-USD": "Cardano",
    "XRP-USD": "Ripple XRP",
    "SHIB-USD": "Shiba Inu coin",
    "AVAX-USD": "Avalanche crypto",
    "DOT-USD": "Polkadot",
    "LINK-USD": "Chainlink",
}


class GoogleTrendsIngestor(BaseIngestor):
    """
    Fetches Google Trends interest-over-time data for crypto keywords.
    Uses pytrends library (free, no API key needed).

    Rate limiting: Google aggressively throttles scrapers.
    We query no more than once per trends_poll_interval (default 1 hour).
    """

    source_name = "google_trends"

    def __init__(self, config: EdgeFactoryConfig):
        self.config = config
        self._last_fetch_times: dict[str, datetime] = {}
        self._cache: dict[str, dict[str, Any]] = {}

    def staleness_threshold(self) -> int:
        return self.config.trends_stale_after

    async def fetch(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """
        Fetch Google Trends interest_over_time for each symbol.

        Returns {symbol: {
            "interest_over_time": list[float],  # daily values (0-100)
            "current_interest": float,           # latest value
            "fetched_at": datetime,
        }}
        """
        now = datetime.now(timezone.utc)

        # Check if we can reuse cached data
        symbols_to_fetch = []
        for sym in symbols:
            if self.is_stale(self._last_fetch_times.get(sym), now):
                symbols_to_fetch.append(sym)

        if symbols_to_fetch:
            fresh_data = await self._fetch_trends(symbols_to_fetch)
            for sym, data in fresh_data.items():
                self._cache[sym] = data
                self._last_fetch_times[sym] = now

        # Return cached data for all requested symbols
        result: dict[str, dict[str, Any]] = {}
        for sym in symbols:
            if sym in self._cache:
                result[sym] = self._cache[sym]
        return result

    async def _fetch_trends(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """Run pytrends query in a thread to avoid blocking the event loop."""
        keywords = []
        sym_map: dict[str, str] = {}  # keyword -> symbol
        for sym in symbols:
            kw = SYMBOL_TO_KEYWORD.get(sym, sym.replace("-USD", ""))
            keywords.append(kw)
            sym_map[kw] = sym

        try:
            data = await asyncio.to_thread(self._query_pytrends, keywords)
            result: dict[str, dict[str, Any]] = {}
            for kw, series in data.items():
                sym = sym_map.get(kw, kw)
                result[sym] = {
                    "interest_over_time": series,
                    "current_interest": series[-1] if series else 0.0,
                    "fetched_at": datetime.now(timezone.utc),
                }
            return result
        except Exception as e:
            logger.warning("Google Trends fetch failed: %s", e)
            return {}

    def _query_pytrends(self, keywords: list[str]) -> dict[str, list[float]]:
        """
        Synchronous pytrends query. Runs in thread pool.
        Queries up to 5 keywords at a time (Google Trends limit).
        """
        try:
            from pytrends.request import TrendReq

            pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 30))

            result: dict[str, list[float]] = {}

            # Google Trends allows max 5 keywords per request
            for i in range(0, len(keywords), 5):
                batch = keywords[i : i + 5]
                pytrends.build_payload(batch, timeframe="now 7-d", geo="")
                df = pytrends.interest_over_time()

                if df.empty:
                    for kw in batch:
                        result[kw] = []
                    continue

                for kw in batch:
                    if kw in df.columns:
                        result[kw] = df[kw].tolist()
                    else:
                        result[kw] = []

            return result

        except ImportError:
            logger.error("pytrends not installed. Run: pip install pytrends")
            return {}
        except Exception as e:
            logger.warning("pytrends query failed: %s", e)
            return {}
