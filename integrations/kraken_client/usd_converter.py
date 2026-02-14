"""Convert any Kraken asset balance to USD.

Uses a cascading price resolution strategy:
  1. Asset is USD → value = amount (1:1)
  2. Direct {ASSET}-USD pair exists → use mid-price
  3. {ASSET}-USDT pair exists → convert via USDT→USD rate
  4. {ASSET}-BTC pair exists → convert via BTC→USD rate
  5. Stablecoin (USDT, USDC, DAI) → assume 1:1
  6. Fallback → $0.00 + log warning (never NaN)

Caches ticker prices for 30 seconds to avoid hammering the API.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import KrakenClient

logger = logging.getLogger(__name__)

# Common assets and their direct USD pair names on Kraken
_DIRECT_USD_PAIRS: dict[str, str] = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "DOGE": "DOGE-USD",
    "ADA": "ADA-USD",
    "DOT": "DOT-USD",
    "AVAX": "AVAX-USD",
    "LINK": "LINK-USD",
    "MATIC": "MATIC-USD",
    "ATOM": "ATOM-USD",
    "UNI": "UNI-USD",
    "LTC": "LTC-USD",
    "XRP": "XRP-USD",
    "SHIB": "SHIB-USD",
    "NEAR": "NEAR-USD",
    "FIL": "FIL-USD",
    "APT": "APT-USD",
    "ARB": "ARB-USD",
    "OP": "OP-USD",
    "TRX": "TRX-USD",
    "PEPE": "PEPE-USD",
    "AAVE": "AAVE-USD",
    "MKR": "MKR-USD",
    "CRV": "CRV-USD",
    "ALGO": "ALGO-USD",
}

_STABLECOINS = {"USDT", "USDC", "DAI", "BUSD", "TUSD", "USDP"}

CACHE_TTL = 30  # seconds


@dataclass
class AssetValue:
    """Result of converting an asset balance to USD."""
    asset: str
    amount: float
    price_usd: float
    value_usd: float


class USDConverter:
    """Converts Kraken asset balances to USD values."""

    def __init__(self, client: "KrakenClient"):
        self.client = client
        self._cache: dict[str, float] = {}
        self._cache_ts: float = 0

    async def _refresh_cache(self) -> None:
        """Refresh the ticker price cache if stale."""
        if time.monotonic() - self._cache_ts < CACHE_TTL and self._cache:
            return

        try:
            # Fetch BTC-USD price first (needed for bridge conversions)
            btc_data = await self.client.get_best_bid_ask("BTC-USD")
            if btc_data:
                mid = (btc_data.get("bid", 0) + btc_data.get("ask", 0)) / 2
                if mid > 0:
                    self._cache["BTC-USD"] = mid

            self._cache_ts = time.monotonic()
        except Exception as e:
            logger.warning("Failed to refresh USD converter cache: %s", e)

    async def get_usd_price(self, asset: str) -> float:
        """Get the USD price for a single asset. Returns 0.0 if unknown."""
        if asset in ("USD", "ZUSD"):
            return 1.0
        if asset in _STABLECOINS:
            return 1.0

        await self._refresh_cache()

        # 1. Check direct USD pair
        pair = _DIRECT_USD_PAIRS.get(asset, f"{asset}-USD")
        if pair in self._cache:
            return self._cache[pair]

        # Try fetching it
        try:
            data = await self.client.get_best_bid_ask(pair)
            if data:
                mid = (data.get("bid", 0) + data.get("ask", 0)) / 2
                if mid > 0:
                    self._cache[pair] = mid
                    return mid
        except Exception:
            pass

        # 2. Try USDT bridge
        try:
            usdt_pair = f"{asset}-USDT"
            data = await self.client.get_best_bid_ask(usdt_pair)
            if data:
                mid = (data.get("bid", 0) + data.get("ask", 0)) / 2
                if mid > 0:
                    self._cache[usdt_pair] = mid
                    return mid  # USDT ≈ USD
        except Exception:
            pass

        # 3. Try BTC bridge
        try:
            btc_pair = f"{asset}-BTC"
            data = await self.client.get_best_bid_ask(btc_pair)
            if data:
                mid = (data.get("bid", 0) + data.get("ask", 0)) / 2
                btc_usd = self._cache.get("BTC-USD", 0)
                if mid > 0 and btc_usd > 0:
                    price = mid * btc_usd
                    self._cache[f"{asset}-USD"] = price
                    return price
        except Exception:
            pass

        logger.warning("Could not determine USD price for %s — returning $0", asset)
        return 0.0

    async def convert_all(self, balances: dict[str, float]) -> list[AssetValue]:
        """Convert all asset balances to USD values.

        Args:
            balances: {asset_name: amount} e.g. {"BTC": 0.5, "ETH": 2.0, "USD": 100.0}

        Returns:
            List of AssetValue with USD prices and values.
        """
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
        """Get current BTC-USD price."""
        await self._refresh_cache()
        return self._cache.get("BTC-USD", 0.0)
