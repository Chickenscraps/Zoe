"""
External Data Service — free API ingestion for alternative indicators.

Sources:
    1. Coinalyze  (funding rates, open interest)  — FREE, no auth, 40 req/min
    2. Alternative.me Fear & Greed Index           — FREE, no auth, 60 req/min

All results are cached in-memory with configurable TTLs to stay well within
rate limits (we only need ~1 call per symbol per candle close cycle).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

# ── Coinalyze symbol mapping ──────────────────────────────────────────
# Zoe universe name → Coinalyze perp symbol (aggregated across exchanges)
_COINALYZE_SYMBOL_MAP = {
    "BTC-USD": "BTCUSD_PERP.A",
    "ETH-USD": "ETHUSD_PERP.A",
    "SOL-USD": "SOLUSD_PERP.A",
    "DOGE-USD": "DOGEUSD_PERP.A",
    "AVAX-USD": "AVAXUSD_PERP.A",
}

_COINALYZE_BASE = "https://api.coinalyze.net/v1"
_FEAR_GREED_URL = "https://api.alternative.me/fng/"


class ExternalDataService:
    """
    Fetches alternative market indicators from free public APIs.

    Usage::

        svc = ExternalDataService()
        funding = await svc.get_funding_rate("BTC-USD")
        fng     = await svc.get_fear_greed_index()
        combo   = await svc.get_all_indicators("BTC-USD")
    """

    def __init__(
        self,
        funding_cache_ttl: float = 28800.0,    # 8 hours
        fear_greed_cache_ttl: float = 86400.0,  # 24 hours
        oi_cache_ttl: float = 3600.0,           # 1 hour
    ):
        self._funding_cache: Dict[str, Dict] = {}
        self._oi_cache: Dict[str, Dict] = {}
        self._fng_cache: Optional[Dict] = None

        self._funding_ttl = funding_cache_ttl
        self._oi_ttl = oi_cache_ttl
        self._fng_ttl = fear_greed_cache_ttl

        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Coinalyze: Funding Rate ──────────────────────────────────────

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Get the latest 8h funding rate for a crypto perpetual.

        Returns the rate as a decimal (e.g. 0.0001 = 0.01%).
        Returns None if unavailable.
        """
        # Check cache
        cached = self._funding_cache.get(symbol)
        if cached and (time.time() - cached["fetched_at"] < self._funding_ttl):
            return cached["rate"]

        coinalyze_sym = _COINALYZE_SYMBOL_MAP.get(symbol)
        if not coinalyze_sym:
            logger.debug("No Coinalyze mapping for %s", symbol)
            return None

        try:
            session = await self._get_session()
            url = f"{_COINALYZE_BASE}/funding-rate?symbols={coinalyze_sym}"
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning("Coinalyze funding rate %s: HTTP %d", symbol, resp.status)
                    return None
                data = await resp.json()

            # Response: [{"symbol": "BTCUSD_PERP.A", "value": 0.0001, ...}]
            if data and isinstance(data, list) and len(data) > 0:
                rate = float(data[0].get("value", 0))
                self._funding_cache[symbol] = {"rate": rate, "fetched_at": time.time()}
                logger.info("Funding rate %s: %.6f", symbol, rate)
                return rate

        except Exception as e:
            logger.warning("Coinalyze funding rate fetch failed for %s: %s", symbol, e)

        return None

    # ── Coinalyze: Open Interest ─────────────────────────────────────

    async def get_open_interest(self, symbol: str) -> Optional[float]:
        """
        Get aggregated open interest (in USD) for a crypto perpetual.
        Returns None if unavailable.
        """
        cached = self._oi_cache.get(symbol)
        if cached and (time.time() - cached["fetched_at"] < self._oi_ttl):
            return cached["oi"]

        coinalyze_sym = _COINALYZE_SYMBOL_MAP.get(symbol)
        if not coinalyze_sym:
            return None

        try:
            session = await self._get_session()
            url = f"{_COINALYZE_BASE}/open-interest?symbols={coinalyze_sym}"
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

            if data and isinstance(data, list) and len(data) > 0:
                oi = float(data[0].get("value", 0))
                self._oi_cache[symbol] = {"oi": oi, "fetched_at": time.time()}
                logger.info("Open interest %s: %.0f", symbol, oi)
                return oi

        except Exception as e:
            logger.warning("Coinalyze OI fetch failed for %s: %s", symbol, e)

        return None

    # ── Alternative.me: Fear & Greed Index ───────────────────────────

    async def get_fear_greed_index(self) -> Optional[int]:
        """
        Get the Crypto Fear & Greed Index (0-100).

        0   = Extreme Fear
        25  = Fear
        50  = Neutral
        75  = Greed
        100 = Extreme Greed

        Returns None if unavailable.
        """
        if self._fng_cache and (time.time() - self._fng_cache["fetched_at"] < self._fng_ttl):
            return self._fng_cache["value"]

        try:
            session = await self._get_session()
            async with session.get(_FEAR_GREED_URL) as resp:
                if resp.status != 200:
                    logger.warning("Fear & Greed API: HTTP %d", resp.status)
                    return None
                data = await resp.json()

            # Response: {"data": [{"value": "25", "value_classification": "Extreme Fear", ...}]}
            items = data.get("data", [])
            if items and len(items) > 0:
                value = int(items[0].get("value", 50))
                classification = items[0].get("value_classification", "Unknown")
                self._fng_cache = {"value": value, "fetched_at": time.time()}
                logger.info("Fear & Greed Index: %d (%s)", value, classification)
                return value

        except Exception as e:
            logger.warning("Fear & Greed fetch failed: %s", e)

        return None

    # ── Combined Indicator Dict ──────────────────────────────────────

    async def get_all_indicators(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch all external indicators for a symbol.

        Returns a dict compatible with bounce catcher's `indicators` parameter::

            {
                "funding_8h":   float | None,   # e.g. 0.0001
                "fear_greed":   int   | None,   # 0-100
                "open_interest": float | None,
            }
        """
        # Fire all requests concurrently
        funding_task = self.get_funding_rate(symbol)
        fng_task = self.get_fear_greed_index()
        oi_task = self.get_open_interest(symbol)

        funding, fng, oi = await asyncio.gather(
            funding_task, fng_task, oi_task,
            return_exceptions=True,
        )

        return {
            "funding_8h": funding if not isinstance(funding, Exception) else None,
            "fear_greed": fng if not isinstance(fng, Exception) else None,
            "open_interest": oi if not isinstance(oi, Exception) else None,
        }
