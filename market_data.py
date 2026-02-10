import os
from typing import Dict, Any, List, Optional
from polygon import RESTClient
from datetime import datetime
import time

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

market_data = MarketData()
