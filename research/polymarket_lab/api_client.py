import httpx
import logging
import asyncio
from typing import List, Optional, Dict, Any
from pytrends.request import TrendReq
from ntscraper import Nitter
from .models import Market

logger = logging.getLogger(__name__)

class PolymarketClient:
    GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
    CLOB_PRICE_URL = "https://clob.polymarket.com/price" # Simplified endpoint for example

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        self.pytrends = TrendReq(hl='en-US', tz=360)
        self.nitter = Nitter(log_level=0)

    async def fetch_active_markets(self, limit: int = 20, min_liquidity: float = 1000) -> List[Market]:
        """Fetch active markets from Gamma API with filters."""
        params = {
            "is_active": "true",
            "limit": limit,
            "order": "volume",
            "ascending": "false"
        }
        try:
            response = await self.client.get(f"{self.GAMMA_BASE_URL}/markets", params=params)
            response.raise_for_status()
            data = response.json()
            
            markets = []
            for m in data:
                # Basic filtering for liquidity to ensure tradeable models
                liquidity = float(m.get("liquidity", 0))
                if liquidity < min_liquidity:
                    continue
                
                markets.append(Market(
                    id=m["id"],
                    question=m["question"],
                    slug=m["slug"],
                    current_yes_price=float(m.get("last_trade_price", 0.5)),
                    volume=float(m.get("volume", 0)),
                    liquidity=liquidity,
                    end_date_iso=m.get("end_date_iso"),
                    category=m.get("category")
                ))
            return markets
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []

    async def get_market_price(self, market_id: str) -> Optional[float]:
        """Fetch current price for a specific market (usually via CLOB or Gamma)."""
        # For simple papertrading, Gamma's last_trade_price or mid_price is often sufficient
        # In a real CLOB, we'd query the book.
        try:
            response = await self.client.get(f"{self.GAMMA_BASE_URL}/markets/{market_id}")
            response.raise_for_status()
            data = response.json()
            return float(data.get("last_trade_price", 0.5))
        except Exception as e:
            logger.error(f"Error fetching price for {market_id}: {e}")
            return None

    async def close(self):
        await self.client.aclose()

    def fetch_trends(self, kw_list: List[str]) -> Dict[str, Any]:
        """Fetch Google Trends interest over time (Synchronous wrapper)."""
        # Pytrends is synchronous, but we can run it in our async client environment
        try:
            self.pytrends.build_payload(kw_list, cat=0, timeframe='now 7-d', geo='', gprop='')
            data = self.pytrends.interest_over_time()
            if data.empty:
                return {}
            # Return last few data points
            return data.tail(5).to_dict()
        except Exception as e:
            logger.error(f"Error fetching trends: {e}")
            return {}

    def fetch_x_posts(self, query: str, limit: int = 20) -> List[str]:
        """Fetch recent posts from X via Nitter scraper."""
        try:
            # Get tweets by term
            results = self.nitter.get_tweets(query, mode='term', number=limit)
            if not results or 'tweets' not in results:
                return []
            
            # Extract text from the list of tweet dictionaries
            return [t.get('text', '') for t in results['tweets']]
        except Exception as e:
            logger.error(f"Error fetching X posts for '{query}': {e}")
            return []
