"""Converts any Kraken asset to USD using ticker data with bridging logic.

Conversion cascade:
  1. Asset is USD → 1:1
  2. Direct {ASSET}USD pair → use ticker mid-price
  3. {ASSET}USDT pair → convert via USDT/USD rate
  4. {ASSET}XBT pair → convert via BTC/USD rate
  5. Fallback → $0.00 + warning
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import KrakenClient


@dataclass
class AssetValue:
    """USD-converted value for a single asset."""
    asset: str
    amount: float
    price_usd: float
    value_usd: float


class USDConverter:
    """Converts Kraken balances to USD with caching."""

    CACHE_TTL = 30  # seconds

    # Common Kraken pair names for USD conversion (base → Kraken pair)
    _DIRECT_USD_PAIRS: dict[str, str] = {
        "BTC": "XBTUSD",
        "ETH": "ETHUSD",
        "XRP": "XRPUSD",
        "SOL": "SOLUSD",
        "DOT": "DOTUSD",
        "ADA": "ADAUSD",
        "MATIC": "MATICUSD",
        "AVAX": "AVAXUSD",
        "LINK": "LINKUSD",
        "DOGE": "DOGEUSD",
        "ATOM": "ATOMUSD",
        "LTC": "LTCUSD",
        "UNI": "UNIUSD",
        "SHIB": "SHIBUSD",
        "XLM": "XLMUSD",
        "NEAR": "NEARUSD",
        "ALGO": "ALGOUSD",
        "FIL": "FILUSD",
        "APE": "APEUSD",
        "MANA": "MANAUSD",
        "SAND": "SANDUSD",
        "CRV": "CRVUSD",
        "AAVE": "AAVEUSD",
        "GRT": "GRTUSD",
        "USDT": "USDTZUSD",
        "USDC": "USDCUSD",
        "DAI": "DAIUSD",
    }

    def __init__(self, client: KrakenClient):
        self.client = client
        self._ticker_cache: dict[str, dict[str, Any]] = {}
        self._cache_ts: float = 0

    async def _refresh_tickers(self) -> None:
        """Fetch all relevant tickers and cache them."""
        now = time.time()
        if self._ticker_cache and (now - self._cache_ts) < self.CACHE_TTL:
            return

        # Build list of pairs we need
        pairs = list(set(self._DIRECT_USD_PAIRS.values()))
        # Also add USDT/USD for bridge conversions
        if "USDTZUSD" not in pairs:
            pairs.append("USDTZUSD")

        try:
            tickers = await self.client.get_ticker(pairs)
            self._ticker_cache = tickers
            self._cache_ts = now
        except Exception as e:
            print(f"[USD-CONV] Ticker fetch failed: {e}")
            # Keep stale cache rather than clearing

    def _mid_price(self, pair_data: dict[str, Any]) -> float:
        """Extract mid-price from Kraken ticker data."""
        try:
            bid = float(pair_data["b"][0])
            ask = float(pair_data["a"][0])
            if bid > 0 and ask > 0:
                return (bid + ask) / 2.0
            # Fallback: last trade price
            return float(pair_data["c"][0])
        except (KeyError, IndexError, ValueError):
            return 0.0

    def _find_ticker(self, pair_name: str) -> dict[str, Any] | None:
        """Find ticker data for a pair, handling Kraken's inconsistent naming."""
        if pair_name in self._ticker_cache:
            return self._ticker_cache[pair_name]
        # Kraken sometimes returns pairs with different naming than requested
        # e.g., request "XBTUSD" but get "XXBTZUSD" in response
        for key, data in self._ticker_cache.items():
            # Normalize and compare
            if pair_name.replace("Z", "").replace("X", "") in key.replace("Z", "").replace("X", ""):
                return data
        return None

    async def get_usd_price(self, asset: str) -> float:
        """Get the USD price for a single asset.

        Returns 0.0 if price cannot be determined (never NaN).
        """
        if asset in ("USD", "ZUSD"):
            return 1.0

        await self._refresh_tickers()

        # 1. Direct USD pair
        direct_pair = self._DIRECT_USD_PAIRS.get(asset)
        if direct_pair:
            ticker = self._find_ticker(direct_pair)
            if ticker:
                price = self._mid_price(ticker)
                if price > 0:
                    return price

        # 2. Try constructing pair name dynamically
        for suffix in ["USD", "ZUSD"]:
            constructed = f"{asset}{suffix}"
            ticker = self._find_ticker(constructed)
            if ticker:
                price = self._mid_price(ticker)
                if price > 0:
                    return price

        # 3. USDT bridge
        for usdt_suffix in ["USDT"]:
            usdt_pair = f"{asset}{usdt_suffix}"
            ticker = self._find_ticker(usdt_pair)
            if ticker:
                asset_usdt = self._mid_price(ticker)
                if asset_usdt > 0:
                    usdt_usd_ticker = self._find_ticker("USDTZUSD")
                    usdt_rate = self._mid_price(usdt_usd_ticker) if usdt_usd_ticker else 1.0
                    if usdt_rate > 0:
                        return asset_usdt * usdt_rate

        # 4. BTC bridge
        for btc_suffix in ["XBT"]:
            btc_pair = f"{asset}{btc_suffix}"
            ticker = self._find_ticker(btc_pair)
            if ticker:
                asset_btc = self._mid_price(ticker)
                if asset_btc > 0:
                    btc_usd_ticker = self._find_ticker("XBTUSD") or self._find_ticker("XXBTZUSD")
                    btc_rate = self._mid_price(btc_usd_ticker) if btc_usd_ticker else 0.0
                    if btc_rate > 0:
                        return asset_btc * btc_rate

        # 5. Stablecoins that should be ~$1
        if asset in ("USDT", "USDC", "DAI", "BUSD"):
            return 1.0

        print(f"[USD-CONV] No USD rate found for {asset}, defaulting to $0")
        return 0.0

    async def convert_all(self, balances: dict[str, float]) -> list[AssetValue]:
        """Convert all balances to USD.

        Args:
            balances: Dict of normalized asset name → amount (e.g., {"BTC": 0.5, "USD": 1000})

        Returns:
            List of AssetValue with USD prices and values.
        """
        await self._refresh_tickers()
        results: list[AssetValue] = []
        for asset, amount in balances.items():
            if amount <= 0:
                continue
            price = await self.get_usd_price(asset)
            results.append(AssetValue(
                asset=asset,
                amount=amount,
                price_usd=price,
                value_usd=amount * price,
            ))
        return results

    async def total_usd(self, balances: dict[str, float]) -> float:
        """Get total USD value of all balances."""
        values = await self.convert_all(balances)
        return sum(v.value_usd for v in values)

    async def btc_price(self) -> float:
        """Get current BTC/USD price."""
        return await self.get_usd_price("BTC")
