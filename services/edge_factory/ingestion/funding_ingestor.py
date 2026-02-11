from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from ..config import EdgeFactoryConfig
from .base import BaseIngestor

logger = logging.getLogger(__name__)

# Robinhood symbol -> OKX perpetual swap instrument ID
SYMBOL_TO_OKX: dict[str, str] = {
    "BTC-USD": "BTC-USDT-SWAP",
    "ETH-USD": "ETH-USDT-SWAP",
    "DOGE-USD": "DOGE-USDT-SWAP",
    "SOL-USD": "SOL-USDT-SWAP",
    "ADA-USD": "ADA-USDT-SWAP",
    "XRP-USD": "XRP-USDT-SWAP",
    "SHIB-USD": "SHIB-USDT-SWAP",
    "AVAX-USD": "AVAX-USDT-SWAP",
    "DOT-USD": "DOT-USDT-SWAP",
    "LINK-USD": "LINK-USDT-SWAP",
}

OKX_BASE = "https://www.okx.com"


class OKXFundingIngestor(BaseIngestor):
    """
    Fetches perpetual futures funding rates and open interest from OKX.

    OKX public API — no authentication required, works from US IPs.
    Rate limit: 20 requests/2s per IP (generous for our polling cadence).

    Endpoints:
    - GET /api/v5/public/funding-rate?instId=BTC-USDT-SWAP
    - GET /api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP
    """

    source_name = "okx"

    def __init__(self, config: EdgeFactoryConfig):
        self.config = config
        self._session: aiohttp.ClientSession | None = None

    def staleness_threshold(self) -> int:
        return self.config.funding_stale_after

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    async def fetch(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """
        Fetch funding rate + open interest for each symbol from OKX.

        Returns {symbol: {
            "funding_rate": float,       # e.g. 0.0001 = 0.01%
            "funding_rate_annual": float, # annualized (rate * 3 * 365)
            "open_interest": float,       # in contracts
            "open_interest_value": float, # in coin-denominated units
            "fetched_at": datetime,
        }}
        """
        result: dict[str, dict[str, Any]] = {}
        session = await self._get_session()

        for sym in symbols:
            okx_inst = SYMBOL_TO_OKX.get(sym)
            if not okx_inst:
                logger.debug("No OKX mapping for %s, skipping", sym)
                continue

            try:
                funding = await self._fetch_funding_rate(session, okx_inst)
                oi = await self._fetch_open_interest(session, okx_inst)

                rate = funding.get("funding_rate", 0.0)
                result[sym] = {
                    "funding_rate": rate,
                    "funding_rate_annual": rate * 3 * 365,  # 8h rate * 3/day * 365
                    "open_interest": oi.get("open_interest", 0.0),
                    "open_interest_value": oi.get("open_interest_value", 0.0),
                    "fetched_at": datetime.now(timezone.utc),
                }
            except Exception as e:
                logger.warning("OKX fetch failed for %s: %s", sym, e)

        return result

    async def _fetch_funding_rate(
        self, session: aiohttp.ClientSession, inst_id: str
    ) -> dict[str, float]:
        url = f"{OKX_BASE}/api/v5/public/funding-rate"
        params = {"instId": inst_id}

        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.warning("OKX funding rate %s: %s %s", inst_id, resp.status, text[:100])
                return {"funding_rate": 0.0}
            data = await resp.json()
            items = data.get("data", [])
            if items:
                return {"funding_rate": float(items[0].get("fundingRate", 0.0))}
            return {"funding_rate": 0.0}

    async def _fetch_open_interest(
        self, session: aiohttp.ClientSession, inst_id: str
    ) -> dict[str, float]:
        url = f"{OKX_BASE}/api/v5/public/open-interest"
        params = {"instType": "SWAP", "instId": inst_id}

        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return {"open_interest": 0.0, "open_interest_value": 0.0}
            data = await resp.json()
            items = data.get("data", [])
            if items:
                oi = float(items[0].get("oi", 0.0))
                oi_ccy = float(items[0].get("oiCcy", 0.0))
                return {
                    "open_interest": oi,
                    "open_interest_value": oi_ccy,
                }
            return {"open_interest": 0.0, "open_interest_value": 0.0}

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
