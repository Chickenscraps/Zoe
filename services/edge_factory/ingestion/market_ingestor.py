from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from ..config import EdgeFactoryConfig
from .base import BaseIngestor

logger = logging.getLogger(__name__)

# Robinhood crypto symbols -> Polygon crypto symbols
SYMBOL_TO_POLYGON: dict[str, str] = {
    "BTC-USD": "X:BTCUSD",
    "ETH-USD": "X:ETHUSD",
    "DOGE-USD": "X:DOGEUSD",
    "SOL-USD": "X:SOLUSD",
    "ADA-USD": "X:ADAUSD",
    "XRP-USD": "X:XRPUSD",
    "SHIB-USD": "X:SHIBUSD",
    "AVAX-USD": "X:AVAXUSD",
    "DOT-USD": "X:DOTUSD",
    "LINK-USD": "X:LINKUSD",
}


class MarketDataIngestor(BaseIngestor):
    """
    Wraps existing Polygon.io market_data.py client and RH get_best_bid_ask.
    Fetches OHLCV bars, current price, and bid/ask spread.
    """

    source_name = "polygon"

    def __init__(self, config: EdgeFactoryConfig, polygon_client: Any = None, rh_client: Any = None):
        self.config = config
        self._polygon = polygon_client  # existing market_data.MarketData instance
        self._rh = rh_client  # existing RobinhoodCryptoClient instance
        self._cache: dict[str, dict[str, Any]] = {}
        self._last_fetch: dict[str, datetime] = {}

    def staleness_threshold(self) -> int:
        return self.config.market_stale_after

    async def fetch(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """
        Fetch market data for each symbol.

        Returns {symbol: {
            "bars_daily": list[dict],    # OHLCV from Polygon
            "current_price": float,
            "bid": float,
            "ask": float,
            "spread": float,             # absolute spread
            "spread_pct": float,         # spread as % of midpoint
            "volume_24h": float,
            "fetched_at": datetime,
        }}
        """
        now = datetime.now(timezone.utc)
        result: dict[str, dict[str, Any]] = {}

        for sym in symbols:
            try:
                data: dict[str, Any] = {"fetched_at": now}

                # Fetch OHLCV bars from Polygon
                if self._polygon is not None:
                    polygon_sym = SYMBOL_TO_POLYGON.get(sym, sym)
                    bars = await asyncio.to_thread(
                        self._polygon.get_history,
                        polygon_sym,
                        timespan="day",
                        multiplier=1,
                        limit=60,  # 60 days of daily bars
                    )
                    data["bars_daily"] = bars

                    # Current price from latest bar
                    if bars:
                        data["current_price"] = bars[-1].get("close", 0.0)
                        data["volume_24h"] = bars[-1].get("volume", 0.0)
                    else:
                        data["current_price"] = 0.0
                        data["volume_24h"] = 0.0
                else:
                    data["bars_daily"] = []
                    data["current_price"] = 0.0
                    data["volume_24h"] = 0.0

                # Fetch bid/ask from Robinhood
                if self._rh is not None:
                    try:
                        bid_ask = await self._rh.get_best_bid_ask(sym)
                        results = bid_ask.get("results", [])
                        if results:
                            entry = results[0] if isinstance(results, list) else bid_ask
                            bid = float(entry.get("bid_inclusive_of_sell_spread", entry.get("bid_price", 0)))
                            ask = float(entry.get("ask_inclusive_of_buy_spread", entry.get("ask_price", 0)))
                        else:
                            bid = 0.0
                            ask = 0.0
                    except Exception as e:
                        logger.warning("RH bid/ask failed for %s: %s", sym, e)
                        bid = 0.0
                        ask = 0.0

                    data["bid"] = bid
                    data["ask"] = ask
                    spread = ask - bid
                    data["spread"] = spread
                    mid = (bid + ask) / 2 if (bid + ask) > 0 else 1.0
                    data["spread_pct"] = spread / mid

                    # Use mid as current price if available and polygon missed
                    if data["current_price"] == 0.0 and mid > 0:
                        data["current_price"] = mid
                else:
                    data["bid"] = 0.0
                    data["ask"] = 0.0
                    data["spread"] = 0.0
                    data["spread_pct"] = 0.0

                result[sym] = data
                self._cache[sym] = data
                self._last_fetch[sym] = now

            except Exception as e:
                logger.warning("Market data fetch failed for %s: %s", sym, e)
                # Return cached data if available
                if sym in self._cache:
                    result[sym] = self._cache[sym]

        return result
