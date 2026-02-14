"""Kraken REST API client with HMAC-SHA512 authentication.

Handles all private/public API calls, rate limiting, and Kraken-specific
asset/pair name normalization.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import aiohttp


# ── Kraken asset name normalization ──────────────────────────────────────────
# Kraken uses legacy prefixed names: XXBT=BTC, XETH=ETH, ZUSD=USD, etc.
# Modern assets (SOL, DOT, MATIC) have no prefix.

_ASSET_MAP: dict[str, str] = {
    "XXBT": "BTC",
    "XBT": "BTC",
    "XETH": "ETH",
    "XXRP": "XRP",
    "XLTC": "LTC",
    "XXLM": "XLM",
    "XXDG": "DOGE",
    "XZEC": "ZEC",
    "XXMR": "XMR",
    "XREP": "REP",
    "XETC": "ETC",
    "ZUSD": "USD",
    "ZEUR": "EUR",
    "ZGBP": "GBP",
    "ZJPY": "JPY",
    "ZCAD": "CAD",
    "ZAUD": "AUD",
    "ZKRW": "KRW",
}

# Reverse map for building Kraken pair names
_ASSET_TO_KRAKEN: dict[str, str] = {v: k for k, v in _ASSET_MAP.items()}
_ASSET_TO_KRAKEN["BTC"] = "XBT"  # Kraken uses XBT in pairs


def normalize_asset(name: str) -> str:
    """Convert Kraken asset name to standard symbol: XXBT → BTC, ZUSD → USD."""
    # Strip staking suffix
    base = name.rstrip(".S").rstrip(".M").rstrip(".P")
    if base in _ASSET_MAP:
        return _ASSET_MAP[base]
    # Strip single X/Z prefix for older assets
    if len(base) == 4 and base[0] in ("X", "Z") and base not in _ASSET_MAP:
        candidate = base[1:]
        if candidate.isalpha():
            return candidate
    return base


def normalize_pair(kraken_pair: str) -> str:
    """Convert Kraken pair to standard format: XXBTZUSD → BTC-USD."""
    # Try known patterns
    for suffix_k, suffix_n in [("ZUSD", "USD"), ("USD", "USD"), ("ZUSDT", "USDT"), ("USDT", "USDT")]:
        if kraken_pair.endswith(suffix_k):
            base_k = kraken_pair[: -len(suffix_k)]
            base_n = normalize_asset(base_k)
            return f"{base_n}-{suffix_n}"
    # Fallback: split at common quote currencies
    for quote in ("USD", "USDT", "EUR", "XBT", "BTC", "ETH"):
        if kraken_pair.endswith(quote):
            base_k = kraken_pair[: -len(quote)]
            base_n = normalize_asset(base_k)
            quote_n = normalize_asset(quote) if quote in _ASSET_MAP else quote
            return f"{base_n}-{quote_n}"
    return kraken_pair


def denormalize_pair(standard_pair: str) -> str:
    """Convert BTC-USD → XBTUSD for Kraken API calls."""
    parts = standard_pair.split("-")
    if len(parts) != 2:
        return standard_pair
    base, quote = parts
    k_base = _ASSET_TO_KRAKEN.get(base, base)
    k_quote = _ASSET_TO_KRAKEN.get(quote, quote)
    return f"{k_base}{k_quote}"


# ── Rate limiter ─────────────────────────────────────────────────────────────

class _RateLimiter:
    """Token bucket rate limiter for Kraken API (Intermediate tier)."""

    def __init__(self, capacity: int = 15, decay_rate: float = 0.33):
        self.capacity = capacity
        self.decay_rate = decay_rate
        self.tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, cost: int = 1) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self.tokens = min(self.capacity, self.tokens + elapsed * self.decay_rate)
            self._last = now
            if self.tokens < cost:
                wait = (cost - self.tokens) / self.decay_rate
                await asyncio.sleep(wait)
                self.tokens = cost
            self.tokens -= cost


# ── Config ───────────────────────────────────────────────────────────────────

@dataclass
class KrakenConfig:
    api_key: str = ""
    api_secret: str = ""  # base64-encoded
    base_url: str = "https://api.kraken.com"
    api_version: str = "0"
    timeout: float = 30.0
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> KrakenConfig:
        return cls(
            api_key=os.getenv("KRAKEN_API_KEY", ""),
            api_secret=os.getenv("KRAKEN_API_SECRET", ""),
        )


# ── Client ───────────────────────────────────────────────────────────────────

class KrakenError(Exception):
    """Raised when Kraken API returns an error."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Kraken API error: {'; '.join(errors)}")


class KrakenClient:
    """Async Kraken REST API client."""

    def __init__(self, config: KrakenConfig | None = None):
        self.cfg = config or KrakenConfig.from_env()
        self._session: aiohttp.ClientSession | None = None
        self._rate = _RateLimiter()
        self._secret_bytes = base64.b64decode(self.cfg.api_secret) if self.cfg.api_secret else b""

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.cfg.timeout)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Auth ─────────────────────────────────────────────────────────────

    def _sign(self, url_path: str, data: dict[str, Any]) -> dict[str, str]:
        """Generate Kraken API-Sign header.

        signature = HMAC-SHA512(
            url_path + SHA256(nonce + post_data),
            base64_decode(api_secret)
        )
        """
        nonce = data["nonce"]
        post_data = urllib.parse.urlencode(data)
        encoded = (str(nonce) + post_data).encode("utf-8")
        message = url_path.encode("utf-8") + hashlib.sha256(encoded).digest()
        signature = hmac.new(self._secret_bytes, message, hashlib.sha512)
        sig_b64 = base64.b64encode(signature.digest()).decode("utf-8")
        return {
            "API-Key": self.cfg.api_key,
            "API-Sign": sig_b64,
        }

    # ── Low-level request methods ────────────────────────────────────────

    async def _public(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """GET /0/public/{endpoint}"""
        url = f"{self.cfg.base_url}/{self.cfg.api_version}/public/{endpoint}"
        await self._rate.acquire(cost=1)
        session = await self._get_session()
        for attempt in range(self.cfg.max_retries):
            try:
                async with session.get(url, params=params) as resp:
                    body = await resp.json()
                    if body.get("error"):
                        raise KrakenError(body["error"])
                    return body.get("result", {})
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == self.cfg.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

    async def _private(self, endpoint: str, data: dict[str, Any] | None = None) -> Any:
        """POST /0/private/{endpoint} with authentication."""
        url_path = f"/{self.cfg.api_version}/private/{endpoint}"
        url = f"{self.cfg.base_url}{url_path}"
        if data is None:
            data = {}
        data["nonce"] = str(int(time.time() * 1000))
        headers = self._sign(url_path, data)
        await self._rate.acquire(cost=1)
        session = await self._get_session()
        for attempt in range(self.cfg.max_retries):
            try:
                async with session.post(url, data=data, headers=headers) as resp:
                    body = await resp.json()
                    if body.get("error"):
                        errors = body["error"]
                        # Rate limit errors → back off
                        if any("EAPI:Rate limit" in e for e in errors):
                            wait = 2 ** (attempt + 1)
                            print(f"[KRAKEN] Rate limited, waiting {wait}s")
                            await asyncio.sleep(wait)
                            # Re-generate nonce for retry
                            data["nonce"] = str(int(time.time() * 1000))
                            headers = self._sign(url_path, data)
                            continue
                        raise KrakenError(errors)
                    return body.get("result", {})
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == self.cfg.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                # Re-generate nonce for retry
                data["nonce"] = str(int(time.time() * 1000))
                headers = self._sign(url_path, data)

    # ── Public endpoints ─────────────────────────────────────────────────

    async def get_ticker(self, pairs: list[str]) -> dict[str, Any]:
        """Get ticker info for one or more pairs.

        Args:
            pairs: List of Kraken pair names (e.g., ["XBTUSD", "ETHUSD"])

        Returns:
            Dict mapping pair → ticker data with keys:
            a=[ask price, whole lot volume, lot volume]
            b=[bid price, whole lot volume, lot volume]
            c=[last trade closed price, lot volume]
            v=[volume today, last 24h]
            p=[vwap today, last 24h]
            t=[number of trades today, last 24h]
            l=[low today, last 24h]
            h=[high today, last 24h]
            o=today's opening price
        """
        return await self._public("Ticker", {"pair": ",".join(pairs)})

    async def get_asset_pairs(self, pairs: list[str] | None = None) -> dict[str, Any]:
        """Get tradeable asset pairs metadata."""
        params = {}
        if pairs:
            params["pair"] = ",".join(pairs)
        return await self._public("AssetPairs", params or None)

    async def get_system_status(self) -> dict[str, Any]:
        """Get Kraken system status."""
        return await self._public("SystemStatus")

    # ── Private endpoints ────────────────────────────────────────────────

    async def get_account_balance(self) -> dict[str, float]:
        """Get all asset balances.

        Returns:
            Dict mapping Kraken asset name → balance (e.g., {"XXBT": 0.5, "ZUSD": 1234.56})
        """
        raw = await self._private("Balance")
        return {k: float(v) for k, v in raw.items()}

    async def get_trade_balance(self, asset: str = "ZUSD") -> dict[str, Any]:
        """Get trade balance summary denominated in given asset.

        Returns dict with keys: eb (equivalent balance), tb (trade balance),
        m (margin), n (unrealized P&L), e (equity), mf (free margin), etc.
        """
        return await self._private("TradeBalance", {"asset": asset})

    async def get_open_orders(self) -> dict[str, Any]:
        """Get all open orders.

        Returns:
            {"open": {txid: order_data, ...}}
        """
        return await self._private("OpenOrders")

    async def get_closed_orders(self, start: int | None = None, end: int | None = None) -> dict[str, Any]:
        """Get closed orders."""
        data: dict[str, Any] = {}
        if start is not None:
            data["start"] = start
        if end is not None:
            data["end"] = end
        return await self._private("ClosedOrders", data)

    async def get_trades_history(self, start: int | None = None, end: int | None = None) -> dict[str, Any]:
        """Get trade history (fills)."""
        data: dict[str, Any] = {}
        if start is not None:
            data["start"] = start
        if end is not None:
            data["end"] = end
        return await self._private("TradesHistory", data)

    async def query_orders(self, txids: list[str]) -> dict[str, Any]:
        """Query specific orders by txid."""
        return await self._private("QueryOrders", {"txid": ",".join(txids)})

    async def get_ws_token(self) -> str:
        """Get WebSocket authentication token (valid ~15 min)."""
        result = await self._private("GetWebSocketsToken")
        return result["token"]

    async def place_order(
        self,
        pair: str,
        side: str,
        ordertype: str,
        volume: float,
        price: float | None = None,
        validate: bool = False,
    ) -> dict[str, Any]:
        """Place an order.

        Args:
            pair: Kraken pair name (e.g., "XBTUSD")
            side: "buy" or "sell"
            ordertype: "market", "limit", "stop-loss", "take-profit", etc.
            volume: Order volume in base currency
            price: Limit price (required for limit orders)
            validate: If True, validate only (don't actually submit)

        Returns:
            {"descr": {"order": "..."}, "txid": ["OXXXX-XXXXX-XXXXXX"]}
        """
        data: dict[str, Any] = {
            "pair": pair,
            "type": side,
            "ordertype": ordertype,
            "volume": str(volume),
        }
        if price is not None:
            data["price"] = str(price)
        if validate:
            data["validate"] = "true"
        return await self._private("AddOrder", data)

    async def cancel_order(self, txid: str) -> dict[str, Any]:
        """Cancel an open order."""
        return await self._private("CancelOrder", {"txid": txid})

    # ── Convenience methods ──────────────────────────────────────────────

    async def get_normalized_balances(self) -> dict[str, float]:
        """Get balances with normalized asset names (BTC, ETH, USD, etc.).

        Filters out zero balances and staking variants.
        """
        raw = await self.get_account_balance()
        result: dict[str, float] = {}
        for asset, qty in raw.items():
            if qty <= 0:
                continue
            # Skip staked variants — they'll be counted under the base asset
            if asset.endswith(".S") or asset.endswith(".M") or asset.endswith(".P"):
                base = normalize_asset(asset)
                result[base] = result.get(base, 0.0) + qty
            else:
                name = normalize_asset(asset)
                result[name] = result.get(name, 0.0) + qty
        return result

    async def get_normalized_open_orders(self) -> list[dict[str, Any]]:
        """Get open orders with normalized pair names and standard fields."""
        raw = await self.get_open_orders()
        orders = raw.get("open", {})
        result = []
        for txid, order in orders.items():
            descr = order.get("descr", {})
            vol = float(order.get("vol", 0))
            vol_exec = float(order.get("vol_exec", 0))
            result.append({
                "order_id": txid,
                "pair": normalize_pair(descr.get("pair", "")),
                "side": descr.get("type", ""),
                "order_type": descr.get("ordertype", ""),
                "price": float(descr.get("price", 0) or 0),
                "volume": vol,
                "filled": vol_exec,
                "remaining": vol - vol_exec,
                "status": order.get("status", "open"),
                "created_at": order.get("opentm", 0),
                "raw": order,
            })
        return result
