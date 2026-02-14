"""Kraken Spot REST API client with HMAC-SHA512 authentication.

Implements all endpoints needed by the trading bot:
- Public: AssetPairs, Ticker, Depth, Time
- Private: Balance, OpenOrders, ClosedOrders, TradesHistory, AddOrder, CancelOrder, GetWebSocketsToken

Authentication follows Kraken's scheme:
  API-Sign = HMAC-SHA512(base64_decode(api_secret), url_path + SHA256(nonce + post_data))

Rate limiting is handled externally by rate_limiter.py (Phase 5).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .symbol_map import normalize_kraken_asset


# ── Data classes ──

@dataclass
class AssetPairInfo:
    symbol: str             # Kraken WS v2 friendly name, e.g. "BTC/USD"
    altname: str            # Kraken altname, e.g. "XBTUSD"
    base: str               # Normalized base, e.g. "BTC"
    quote: str              # Normalized quote, e.g. "USD"
    lot_decimals: int
    pair_decimals: int
    lot_min: float
    cost_min: float
    ordermin: float
    tick_size: float | None
    status: str             # "online", "cancel_only", etc.


@dataclass
class TickerData:
    symbol: str
    bid: float
    ask: float
    last: float
    volume_24h: float
    vwap_24h: float
    high_24h: float
    low_24h: float
    open_24h: float
    trades_24h: int


@dataclass
class OrderInfo:
    order_id: str
    symbol: str
    side: str               # "buy" or "sell"
    order_type: str         # "limit" or "market"
    price: float
    qty: float
    filled_qty: float
    status: str             # "open", "closed", "canceled", "expired"
    client_order_id: str | None
    open_time: float
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeInfo:
    trade_id: str
    order_id: str
    symbol: str
    side: str
    qty: float
    price: float
    fee: float
    fee_currency: str
    timestamp: float
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResult:
    order_id: str
    status: str
    description: str
    raw: dict[str, Any] = field(default_factory=dict)


# ── Exceptions ──

class KrakenAPIError(Exception):
    """Raised when Kraken returns an error response."""
    def __init__(self, errors: list[str], endpoint: str = ""):
        self.errors = errors
        self.endpoint = endpoint
        super().__init__(f"Kraken API error on {endpoint}: {', '.join(errors)}")


class KrakenRateLimitError(KrakenAPIError):
    """Raised specifically for EAPI:Rate limit exceeded."""
    pass


# ── Client ──

class KrakenRestClient:
    """Async Kraken Spot REST API client."""

    BASE_URL = "https://api.kraken.com"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        base_url: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session: aiohttp.ClientSession | None = None
        # Nonce must be strictly increasing; use millisecond timestamp
        self._last_nonce: int = 0

    # ── Session management ──

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Auth helpers ──

    def _get_nonce(self) -> int:
        nonce = int(time.time() * 1000)
        if nonce <= self._last_nonce:
            nonce = self._last_nonce + 1
        self._last_nonce = nonce
        return nonce

    def _sign(self, url_path: str, data: dict[str, Any], nonce: int) -> str:
        """Compute HMAC-SHA512 signature per Kraken spec."""
        post_data = urllib.parse.urlencode(data)
        encoded = (str(nonce) + post_data).encode("utf-8")
        message = url_path.encode("utf-8") + hashlib.sha256(encoded).digest()
        secret = base64.b64decode(self.api_secret)
        mac = hmac.new(secret, message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode("utf-8")

    # ── HTTP helpers ──

    async def _public_request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a public (unauthenticated) GET/POST request."""
        url = f"{self.base_url}/0/public/{endpoint}"
        session = await self._get_session()

        for attempt in range(self.max_retries):
            try:
                async with session.post(url, data=params or {}) as resp:
                    data = await resp.json()
                    errors = data.get("error", [])
                    if errors:
                        if any("EAPI:Rate limit" in e for e in errors):
                            raise KrakenRateLimitError(errors, endpoint)
                        raise KrakenAPIError(errors, endpoint)
                    return data.get("result", {})
            except (aiohttp.ClientError, KrakenRateLimitError) as e:
                if attempt == self.max_retries - 1:
                    raise
                wait = self.retry_delay * (2 ** attempt)
                await _async_sleep(wait)

        return {}  # unreachable

    async def _private_request(self, endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make an authenticated POST request."""
        if not self.api_key or not self.api_secret:
            raise KrakenAPIError(["Missing API key or secret"], endpoint)

        url_path = f"/0/private/{endpoint}"
        url = f"{self.base_url}{url_path}"
        nonce = self._get_nonce()

        post_data = dict(data or {})
        post_data["nonce"] = nonce

        signature = self._sign(url_path, post_data, nonce)
        headers = {
            "API-Key": self.api_key,
            "API-Sign": signature,
        }

        session = await self._get_session()

        for attempt in range(self.max_retries):
            try:
                async with session.post(url, data=post_data, headers=headers) as resp:
                    result = await resp.json()
                    errors = result.get("error", [])
                    if errors:
                        if any("EAPI:Rate limit" in e for e in errors):
                            raise KrakenRateLimitError(errors, endpoint)
                        raise KrakenAPIError(errors, endpoint)
                    return result.get("result", {})
            except (aiohttp.ClientError, KrakenRateLimitError) as e:
                if attempt == self.max_retries - 1:
                    raise
                wait = self.retry_delay * (2 ** attempt)
                await _async_sleep(wait)

        return {}  # unreachable

    # ── Public endpoints ──

    async def get_server_time(self) -> dict[str, Any]:
        """GET /0/public/Time — connectivity check."""
        return await self._public_request("Time")

    async def get_asset_pairs(self) -> list[AssetPairInfo]:
        """GET /0/public/AssetPairs — all tradeable pairs with metadata."""
        result = await self._public_request("AssetPairs")
        pairs: list[AssetPairInfo] = []
        for key, info in result.items():
            wsname = info.get("wsname", "")
            if not wsname or "/" not in wsname:
                continue
            base_raw, quote_raw = wsname.split("/", 1)
            base = normalize_kraken_asset(base_raw)
            quote = normalize_kraken_asset(quote_raw)
            pairs.append(AssetPairInfo(
                symbol=f"{base}/{quote}",
                altname=info.get("altname", key),
                base=base,
                quote=quote,
                lot_decimals=int(info.get("lot_decimals", 8)),
                pair_decimals=int(info.get("pair_decimals", 1)),
                lot_min=float(info.get("lot_minimum", info.get("ordermin", 0))),
                cost_min=float(info.get("costmin", 0)),
                ordermin=float(info.get("ordermin", 0)),
                tick_size=float(info["tick_size"]) if "tick_size" in info else None,
                status=info.get("status", "online"),
            ))
        return pairs

    async def get_ticker(self, symbols: list[str]) -> dict[str, TickerData]:
        """POST /0/public/Ticker — current ticker for given pairs.

        Args:
            symbols: List of Kraken pair names (e.g. ["XBTUSD", "ETHUSD"])
                     or altnames. The API accepts comma-separated pair strings.
        """
        result = await self._public_request("Ticker", {"pair": ",".join(symbols)})
        tickers: dict[str, TickerData] = {}
        for key, info in result.items():
            tickers[key] = TickerData(
                symbol=key,
                bid=float(info["b"][0]),       # best bid [price, whole_lot_volume, lot_volume]
                ask=float(info["a"][0]),        # best ask
                last=float(info["c"][0]),       # last trade price
                volume_24h=float(info["v"][1]), # volume today (24h)
                vwap_24h=float(info["p"][1]),   # vwap 24h
                high_24h=float(info["h"][1]),
                low_24h=float(info["l"][1]),
                open_24h=float(info["o"]),
                trades_24h=int(info["t"][1]),
            )
        return tickers

    async def get_order_book(self, pair: str, count: int = 10) -> dict[str, Any]:
        """POST /0/public/Depth — order book snapshot."""
        return await self._public_request("Depth", {"pair": pair, "count": count})

    # ── Private endpoints ──

    async def get_balance(self) -> dict[str, float]:
        """POST /0/private/Balance — all asset balances.

        Returns dict with normalized asset names, e.g. {"BTC": 0.5, "USD": 1000.0}.
        """
        result = await self._private_request("Balance")
        balances: dict[str, float] = {}
        for asset, amount in result.items():
            name = normalize_kraken_asset(asset)
            val = float(amount)
            if val != 0.0:
                balances[name] = balances.get(name, 0.0) + val
        return balances

    async def get_open_orders(self) -> list[OrderInfo]:
        """POST /0/private/OpenOrders — current working orders."""
        result = await self._private_request("OpenOrders")
        orders_raw = result.get("open", {})
        orders: list[OrderInfo] = []
        for oid, info in orders_raw.items():
            descr = info.get("descr", {})
            orders.append(OrderInfo(
                order_id=oid,
                symbol=descr.get("pair", ""),
                side=descr.get("type", ""),
                order_type=descr.get("ordertype", ""),
                price=float(descr.get("price", 0)),
                qty=float(info.get("vol", 0)),
                filled_qty=float(info.get("vol_exec", 0)),
                status=info.get("status", "open"),
                client_order_id=info.get("userref"),
                open_time=float(info.get("opentm", 0)),
                raw=info,
            ))
        return orders

    async def get_closed_orders(self, start: float | None = None) -> list[OrderInfo]:
        """POST /0/private/ClosedOrders — recently closed orders."""
        params: dict[str, Any] = {}
        if start is not None:
            params["start"] = start
        result = await self._private_request("ClosedOrders", params)
        orders_raw = result.get("closed", {})
        orders: list[OrderInfo] = []
        for oid, info in orders_raw.items():
            descr = info.get("descr", {})
            orders.append(OrderInfo(
                order_id=oid,
                symbol=descr.get("pair", ""),
                side=descr.get("type", ""),
                order_type=descr.get("ordertype", ""),
                price=float(descr.get("price", 0)),
                qty=float(info.get("vol", 0)),
                filled_qty=float(info.get("vol_exec", 0)),
                status=info.get("status", "closed"),
                client_order_id=info.get("userref"),
                open_time=float(info.get("opentm", 0)),
                raw=info,
            ))
        return orders

    async def get_trades_history(self, start: float | None = None) -> list[TradeInfo]:
        """POST /0/private/TradesHistory — filled trades."""
        params: dict[str, Any] = {}
        if start is not None:
            params["start"] = start
        result = await self._private_request("TradesHistory", params)
        trades_raw = result.get("trades", {})
        trades: list[TradeInfo] = []
        for tid, info in trades_raw.items():
            trades.append(TradeInfo(
                trade_id=tid,
                order_id=info.get("ordertxid", ""),
                symbol=info.get("pair", ""),
                side=info.get("type", ""),
                qty=float(info.get("vol", 0)),
                price=float(info.get("price", 0)),
                fee=float(info.get("fee", 0)),
                fee_currency=info.get("fee_currency", "USD"),
                timestamp=float(info.get("time", 0)),
                raw=info,
            ))
        return trades

    async def add_order(
        self,
        pair: str,
        side: str,
        order_type: str,
        volume: float,
        price: float | None = None,
        client_order_id: str | None = None,
        validate: bool = False,
    ) -> OrderResult:
        """POST /0/private/AddOrder — place a new order.

        Args:
            pair: Kraken pair name (e.g. "XBTUSD" or use altname).
            side: "buy" or "sell".
            order_type: "market" or "limit".
            volume: Order quantity in base currency units.
            price: Limit price (required for limit orders).
            client_order_id: Optional cl_ord_id for idempotency.
            validate: If True, validate only (no order placed). Used for testing.
        """
        data: dict[str, Any] = {
            "pair": pair,
            "type": side,
            "ordertype": order_type,
            "volume": str(volume),
        }
        if price is not None:
            data["price"] = str(price)
        if client_order_id:
            data["cl_ord_id"] = client_order_id
        if validate:
            data["validate"] = "true"

        result = await self._private_request("AddOrder", data)
        txid_list = result.get("txid", [])
        return OrderResult(
            order_id=txid_list[0] if txid_list else "",
            status="submitted",
            description=result.get("descr", {}).get("order", ""),
            raw=result,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """POST /0/private/CancelOrder — cancel a single order."""
        result = await self._private_request("CancelOrder", {"txid": order_id})
        count = result.get("count", 0)
        return count > 0

    async def cancel_all_orders(self) -> int:
        """POST /0/private/CancelAll — cancel all open orders."""
        result = await self._private_request("CancelAll")
        return result.get("count", 0)

    async def get_ws_token(self) -> str:
        """POST /0/private/GetWebSocketsToken — get auth token for private WS.

        Requires API key with 'WebSocket Interface' permission enabled.
        Token expires after ~15 minutes of inactivity.
        """
        result = await self._private_request("GetWebSocketsToken")
        token = result.get("token", "")
        if not token:
            raise KrakenAPIError(["No WS token returned"], "GetWebSocketsToken")
        return token


# ── Utility ──

async def _async_sleep(seconds: float) -> None:
    """Async sleep wrapper (avoids import at top level for minimal deps)."""
    import asyncio
    await asyncio.sleep(seconds)
