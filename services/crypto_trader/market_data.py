from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from dataclasses import dataclass

from integrations.robinhood_crypto_client import RobinhoodCryptoClient

# Simple in-memory cache for candles to reduce calls
# Key: (symbol, timeframe) -> (timestamp, candles)

@dataclass
class Candle:
    symbol: str
    timeframe: str
    bucket: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_final: bool

class MarketDataProvider:
    def __init__(self, client: RobinhoodCryptoClient, repo: Any = None):
        self.client = client
        self.repo = repo  # SupabaseCryptoRepository
        self._cache = {}

    async def get_current_price(self, symbol: str) -> float:
        """Fetch real-time best bid/ask and return mid-price."""
        try:
            quote = await self.client.get_best_bid_ask(symbol)
            # data structure: {'results': [{'symbol': 'BTC-USD', 'price': '...', ...}]} or similar
            # Expected RH Crypto response: {'results': [{'symbol': 'BTC-USD', 'bid_price': '...', 'ask_price': '...', ...}]}
            results = quote.get("results", [])
            if not results:
                return 0.0
            
            data = results[0]
            bid = float(data.get("bid_price", 0))
            ask = float(data.get("ask_price", 0))
            if bid > 0 and ask > 0:
                return (bid + ask) / 2
            return float(data.get("price", 0)) # Fallback
        except Exception as e:
            print(f"⚠️ Failed to get price for {symbol}: {e}")
            return 0.0

    async def get_candles(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> List[Candle]:
        """
        Fetch candles from database if available/fresh, otherwise ideally fetch from source.
        RH Crypto API historicals are tricky. We might rely on Polygon or just 
        build candles from tick data if needed. 
        
        For this simulation/alpha, we will implement a 'Mock' or 'Polygon' fallback if configured, 
        or use Supabase candles that we build up over time.
        
        If 'repo' has fetch_candles, use it.
        """
        if self.repo:
            return await self.repo.fetch_candles(symbol, timeframe, limit)
        return []

    async def update_candle_cache(self, symbol: str, price: float):
        """
        Upsert current price into the 'current' candle in DB.
        This is a simplified way to build OHLCV if we rely on polling.
        """
        # TODO: Implement real-time bar building
        pass
