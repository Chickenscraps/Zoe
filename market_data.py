import os
from typing import Dict, Any, List, Optional, Tuple
from polygon import RESTClient
from datetime import datetime, timedelta
import time

# ── Symbol mapping: Zoe universe name → Polygon crypto ticker ────────
_CRYPTO_SYMBOL_MAP = {
    "BTC-USD": "X:BTCUSD",
    "ETH-USD": "X:ETHUSD",
    "SOL-USD": "X:SOLUSD",
    "DOGE-USD": "X:DOGEUSD",
    "AVAX-USD": "X:AVAXUSD",
}

# ── Timeframe parsing: human-readable → (multiplier, timespan) ───────
_TIMEFRAME_MAP = {
    "1m":  (1,  "minute"),
    "5m":  (5,  "minute"),
    "15m": (15, "minute"),
    "30m": (30, "minute"),
    "1h":  (1,  "hour"),
    "4h":  (4,  "hour"),
    "1d":  (1,  "day"),
}


class MarketData:
    def __init__(self):
        self.api_key = os.getenv("POLYGON_API_KEY")
        if not self.api_key:
            print("⚠️ MarketData: POLYGON_API_KEY missing. Data validation will fail.")
            self.client = None
        else:
            self.client = RESTClient(self.api_key)
            print("✅ MarketData: Polygon client initialized.")

        # Simple in-memory cache for quotes (ttl=10s)
        self.quote_cache = {}
        self.cache_ttl = 10

        # Crypto bar cache: (symbol, timeframe) -> {"bars": [...], "fetched_at": float}
        self._crypto_bar_cache: Dict[Tuple[str, str], Dict] = {}
        self._crypto_bar_cache_ttl = 60  # seconds

    def get_price(self, symbol: str) -> float:
        """Get real-time price for a symbol."""
        if not self.client: return 0.0
        
        # Check cache
        cached = self.quote_cache.get(symbol)
        if cached and (time.time() - cached['timestamp'] < self.cache_ttl):
            return cached['price']

        try:
            # Polygon Last Trade
            trade = self.client.get_last_trade(symbol)
            price = trade.price
            
            # Update cache
            self.quote_cache[symbol] = {
                'price': price,
                'timestamp': time.time()
            }
            return price
        except Exception as e:
            print(f"❌ MarketData Error ({symbol}): {e}")
            return 0.0

    def get_history(self, symbol: str, timespan: str = 'day', multiplier: int = 1, limit: int = 100) -> List[Dict]:
        """Fetch historical bars (aggregates) for TA."""
        if not self.client: return []
        
        try:
            # Calculate from/to dates?
            # client.list_aggs(...)
            # For simplicity, we just ask for last N days
            # Note: Polygon-api-client wrapper handles date logic if we use list_aggs
            # But let's use a simpler approach if possible
            # We need to construct from_date/to_date
            
            # Using defaults for now (standard daily bars)
            aggs = []
            for a in self.client.list_aggs(symbol, multiplier, timespan, "2024-01-01", "2026-12-31", limit=limit, sort='desc'):
                aggs.append({
                    'timestamp': a.timestamp,
                    'open': a.open,
                    'high': a.high,
                    'low': a.low,
                    'close': a.close,
                    'volume': a.volume
                })
            # Reverse to be chronological (oldest first) for TA lib
            return aggs[::-1]
        except Exception as e:
            print(f"❌ History Fetch Error ({symbol}): {e}")
            return []

    def get_option_chain_snapshot(self, symbol: str) -> List[Dict]:
        """
        Fetch Option Chain Snapshot (Values + Greeks).
        This endpoint returns universal snapshot for options of a symbol.
        """
        if not self.client: return []
        
        try:
            # client.list_snapshot_options_chain(underlying_asset, params...)
            # We filter for near-term expiries (e.g., next 45 days)
            # Actually, standard snapshot gets ALL or we can filter.
            # We want to iterate and filter in memory if necessary, or pass params.
            
            chain = []
            # Note: This might be heavy. In production, use filters.
            # Assuming client has list_snapshot_options_chain
            # We iterate manually
            count = 0
            for opt in self.client.list_snapshot_options_chain(symbol, params={"limit": 250}):
                # Extract Greeks if available
                greeks = opt.greeks or {}
                chain.append({
                    'ticker': opt.details.ticker if opt.details else opt.ticker,
                    'expiry': opt.details.expiration_date if opt.details else None,
                    'strike': opt.details.strike_price if opt.details else None,
                    'type': opt.details.contract_type if opt.details else None, # call/put
                    'price': opt.day.close if opt.day else 0.0, # Approximate
                    'implied_volatility': opt.implied_volatility,
                    'delta': greeks.get('delta'),
                    'theta': greeks.get('theta'),
                    'gamma': greeks.get('gamma'),
                    'vega': greeks.get('vega'),
                    'bid': opt.last_quote.bid_price if opt.last_quote else 0,
                    'ask': opt.last_quote.ask_price if opt.last_quote else 0
                })
                count += 1
                if count >= 250: break # Safety limit for dev
            
            return chain

        except Exception as e:
            print(f"❌ Option Chain Error ({symbol}): {e}")
            return []

    # ── Crypto Bars (Polygon Crypto Aggregates) ────────────────────────

    def _to_polygon_crypto(self, symbol: str) -> str:
        """Map 'BTC-USD' → 'X:BTCUSD' for Polygon crypto endpoints."""
        mapped = _CRYPTO_SYMBOL_MAP.get(symbol)
        if mapped:
            return mapped
        # Fallback: try to construct it
        if "-USD" in symbol:
            base = symbol.replace("-USD", "")
            return f"X:{base}USD"
        return symbol

    def _parse_timeframe(self, timeframe: str) -> Tuple[int, str]:
        """Parse '15m' → (15, 'minute'), '1h' → (1, 'hour'), etc."""
        result = _TIMEFRAME_MAP.get(timeframe)
        if result:
            return result
        raise ValueError(f"Unknown timeframe '{timeframe}'. Supported: {list(_TIMEFRAME_MAP.keys())}")

    def get_crypto_bars(self, symbol: str, timeframe: str = "15m", limit: int = 200) -> List[Dict]:
        """
        Fetch crypto OHLCV bars from Polygon.

        Args:
            symbol:    Zoe-format symbol e.g. "BTC-USD"
            timeframe: One of 1m, 5m, 15m, 30m, 1h, 4h, 1d
            limit:     Max bars to return (default 200)

        Returns:
            List of dicts with keys: timestamp, open, high, low, close, volume
            Sorted chronologically (oldest first).
        """
        if not self.client:
            return []

        # Check cache
        cache_key = (symbol, timeframe)
        cached = self._crypto_bar_cache.get(cache_key)
        if cached and (time.time() - cached["fetched_at"] < self._crypto_bar_cache_ttl):
            return cached["bars"]

        try:
            poly_symbol = self._to_polygon_crypto(symbol)
            multiplier, timespan = self._parse_timeframe(timeframe)

            # Date range: go back far enough to get `limit` bars
            # For minute bars, 200 × 15m = 3000 min ≈ 2.1 days; use 7 days for safety
            # For hour bars, 200 × 1h = 200h ≈ 8.3 days; use 14 days
            # For day bars, 200 × 1d = 200 days; use 250 days
            if timespan == "minute":
                lookback_days = max(7, (limit * multiplier) // 1440 + 3)
            elif timespan == "hour":
                lookback_days = max(14, (limit * multiplier) // 24 + 3)
            else:
                lookback_days = limit + 50

            to_date = datetime.utcnow().strftime("%Y-%m-%d")
            from_date = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

            aggs = []
            for a in self.client.list_aggs(
                poly_symbol,
                multiplier,
                timespan,
                from_date,
                to_date,
                limit=limit,
                sort="desc",
            ):
                aggs.append({
                    "timestamp": a.timestamp,
                    "open": float(a.open),
                    "high": float(a.high),
                    "low": float(a.low),
                    "close": float(a.close),
                    "volume": float(a.volume) if a.volume else 0.0,
                })
                if len(aggs) >= limit:
                    break

            # Reverse to chronological (oldest first)
            bars = aggs[::-1]

            # Update cache
            self._crypto_bar_cache[cache_key] = {
                "bars": bars,
                "fetched_at": time.time(),
            }

            return bars

        except Exception as e:
            print(f"❌ Crypto Bars Error ({symbol} {timeframe}): {e}")
            return []

    def get_crypto_price(self, symbol: str) -> float:
        """Get latest crypto price from Polygon (last trade)."""
        if not self.client:
            return 0.0

        poly_symbol = self._to_polygon_crypto(symbol)

        # Check quote cache
        cached = self.quote_cache.get(poly_symbol)
        if cached and (time.time() - cached["timestamp"] < self.cache_ttl):
            return cached["price"]

        try:
            trade = self.client.get_last_crypto_trade(poly_symbol)
            price = float(trade.price)
            self.quote_cache[poly_symbol] = {"price": price, "timestamp": time.time()}
            return price
        except Exception as e:
            # Fallback: use last bar close
            bars = self.get_crypto_bars(symbol, "1m", 1)
            if bars:
                return bars[-1]["close"]
            print(f"❌ Crypto Price Error ({symbol}): {e}")
            return 0.0


market_data = MarketData()
