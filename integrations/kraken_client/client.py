"""Async Kraken REST client with HMAC-SHA512 request signing.

Implements the ExchangeClient protocol so it can be used as a drop-in
replacement for RobinhoodCryptoClient in the trading engines.

Signing algorithm (Kraken standard):
    message = urlpath + SHA256(nonce + postdata)
    signature = HMAC-SHA512(message, base64_decode(api_secret))
    header: API-Sign = base64_encode(signature)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, Optional

import aiohttp

from .config import KrakenConfig, REDACTED_HEADERS
from .symbols import to_kraken, from_kraken, populate_from_asset_pairs

logger = logging.getLogger(__name__)


class _RateLimiter:
    """Token-bucket rate limiter matching Kraken's call counter model.

    Kraken Starter tier: 15 burst, decays at +1 counter per 3 seconds.
    """

    def __init__(self, burst: int = 15, decay_sec: float = 3.0):
        self._max = burst
        self._tokens = float(burst)
        self._decay_sec = decay_sec
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, cost: int = 1) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            refill = elapsed / self._decay_sec
            self._tokens = min(self._max, self._tokens + refill)
            self._last_refill = now

            if self._tokens < cost:
                wait = (cost - self._tokens) * self._decay_sec
                logger.debug("Rate limiter: waiting %.1fs", wait)
                await asyncio.sleep(wait)
                self._tokens = cost  # after sleeping, we have enough

            self._tokens -= cost


class KrakenClient:
    """Async Kraken REST API client with HMAC-SHA512 signing."""

    def __init__(self, config: KrakenConfig):
        self._config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._nonce_offset: int = 0
        self._rate_limiter = _RateLimiter(
            burst=config.rate_limit_burst,
            decay_sec=config.rate_limit_decay_sec,
        )
        self._pairs_loaded = False

    # ── Session Management ─────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._config.timeout_seconds)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ── Signing ────────────────────────────────────────────────

    def _get_nonce(self) -> str:
        """Generate a nonce (monotonically increasing)."""
        return str(int(time.time() * 1000) + self._nonce_offset)

    def _sign(self, urlpath: str, data: dict[str, Any]) -> str:
        """Compute Kraken HMAC-SHA512 signature.

        message = urlpath + SHA256(nonce + postdata)
        signature = HMAC-SHA512(message, base64_decode(secret))
        """
        postdata = urllib.parse.urlencode(data)
        # SHA256(nonce + postdata)
        sha256_hash = hashlib.sha256(
            (str(data["nonce"]) + postdata).encode("utf-8")
        ).digest()
        # message = urlpath_bytes + sha256_hash
        message = urlpath.encode("utf-8") + sha256_hash
        # HMAC-SHA512 with decoded secret
        secret_decoded = base64.b64decode(self._config.api_secret)
        mac = hmac.new(secret_decoded, message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode("utf-8")

    # ── HTTP Methods ───────────────────────────────────────────

    async def _public_request(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Make a public (unauthenticated) GET request."""
        await self._rate_limiter.acquire(cost=1)
        session = await self._get_session()
        url = f"{self._config.base_url}{endpoint}"

        for attempt in range(self._config.max_retries):
            try:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    if data.get("error") and len(data["error"]) > 0:
                        errors = data["error"]
                        # Rate limit errors get retried
                        if any("EAPI:Rate limit" in e for e in errors):
                            wait = 2 ** (attempt + 1)
                            logger.warning("Rate limited, retrying in %ds", wait)
                            await asyncio.sleep(wait)
                            continue
                        raise KrakenAPIError(errors)
                    return data.get("result", {})
            except aiohttp.ClientError as e:
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        raise KrakenAPIError(["Max retries exceeded"])

    async def _private_request(
        self, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Make a private (authenticated) POST request."""
        await self._rate_limiter.acquire(cost=1)
        session = await self._get_session()
        url = f"{self._config.base_url}{endpoint}"

        if data is None:
            data = {}
        data["nonce"] = self._get_nonce()

        signature = self._sign(endpoint, data)
        headers = {
            "API-Key": self._config.api_key,
            "API-Sign": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        for attempt in range(self._config.max_retries):
            try:
                # Must regenerate nonce on retry
                if attempt > 0:
                    data["nonce"] = self._get_nonce()
                    signature = self._sign(endpoint, data)
                    headers["API-Sign"] = signature

                async with session.post(url, data=data, headers=headers) as resp:
                    result = await resp.json()
                    if result.get("error") and len(result["error"]) > 0:
                        errors = result["error"]
                        if any("EAPI:Rate limit" in e for e in errors):
                            wait = 2 ** (attempt + 1)
                            logger.warning("Rate limited, retrying in %ds", wait)
                            await asyncio.sleep(wait)
                            continue
                        if any("EAPI:Invalid nonce" in e for e in errors):
                            # Bump nonce offset and retry
                            self._nonce_offset += 1000
                            logger.warning("Invalid nonce, bumping offset and retrying")
                            continue
                        raise KrakenAPIError(errors)
                    return result.get("result", {})
            except aiohttp.ClientError as e:
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        raise KrakenAPIError(["Max retries exceeded"])

    # ── Public API ─────────────────────────────────────────────

    async def get_system_status(self) -> dict[str, Any]:
        """GET /0/public/SystemStatus"""
        return await self._public_request("/0/public/SystemStatus")

    async def get_trading_pairs(
        self, symbols: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """GET /0/public/AssetPairs — discover tradable pairs.

        Returns full AssetPairs result dict.
        If symbols provided, filters to those pairs.
        """
        params: dict[str, Any] = {}
        if symbols:
            kraken_symbols = [to_kraken(s) for s in symbols]
            params["pair"] = ",".join(kraken_symbols)

        result = await self._public_request("/0/public/AssetPairs", params)

        # Populate symbol cache on first call
        if not self._pairs_loaded and result:
            populate_from_asset_pairs(result)
            self._pairs_loaded = True

        return result

    async def get_best_bid_ask(self, symbol: str) -> dict[str, Any]:
        """GET /0/public/Ticker — get bid/ask for a single pair.

        Returns normalized format compatible with RH client consumers:
        {"results": [{"bid_price": str, "ask_price": str, "symbol": str}]}
        """
        kraken_pair = to_kraken(symbol)
        result = await self._public_request(
            "/0/public/Ticker", {"pair": kraken_pair}
        )

        # Kraken returns: {"XXBTZUSD": {"a": ["price", "whole_lot", "lot"], "b": [...]}}
        for pair_key, ticker in result.items():
            ask_price = ticker["a"][0]  # [price, whole_lot_volume, lot_volume]
            bid_price = ticker["b"][0]
            return {
                "results": [
                    {
                        "symbol": symbol,
                        "bid_price": bid_price,
                        "ask_price": ask_price,
                        "bid_inclusive_of_sell_spread": bid_price,
                        "ask_inclusive_of_buy_spread": ask_price,
                        "last_trade_price": ticker.get("c", ["0"])[0],
                        "volume_24h": ticker.get("v", ["0", "0"])[1],
                        "vwap_24h": ticker.get("p", ["0", "0"])[1],
                        "high_24h": ticker.get("h", ["0", "0"])[1],
                        "low_24h": ticker.get("l", ["0", "0"])[1],
                        "num_trades_24h": ticker.get("t", [0, 0])[1],
                    }
                ]
            }

        return {"results": []}

    async def get_best_bid_ask_batch(
        self, symbols: list[str]
    ) -> dict[str, Any]:
        """GET /0/public/Ticker for multiple pairs in one call.

        Returns: {"results": [{"symbol": ..., "bid_price": ..., ...}, ...]}
        """
        if not symbols:
            return {"results": []}

        kraken_pairs = [to_kraken(s) for s in symbols]
        result = await self._public_request(
            "/0/public/Ticker", {"pair": ",".join(kraken_pairs)}
        )

        results = []
        for pair_key, ticker in result.items():
            internal_symbol = from_kraken(pair_key)
            results.append(
                {
                    "symbol": internal_symbol,
                    "bid_price": ticker["b"][0],
                    "ask_price": ticker["a"][0],
                    "bid_inclusive_of_sell_spread": ticker["b"][0],
                    "ask_inclusive_of_buy_spread": ticker["a"][0],
                    "last_trade_price": ticker.get("c", ["0"])[0],
                    "volume_24h": ticker.get("v", ["0", "0"])[1],
                    "vwap_24h": ticker.get("p", ["0", "0"])[1],
                    "high_24h": ticker.get("h", ["0", "0"])[1],
                    "low_24h": ticker.get("l", ["0", "0"])[1],
                }
            )

        return {"results": results}

    # ── Private API ────────────────────────────────────────────

    async def get_account_balances(self) -> dict[str, Any]:
        """POST /0/private/Balance — get all asset balances.

        Returns: {"ZUSD": "1234.56", "XXBT": "0.5", ...}
        """
        return await self._private_request("/0/private/Balance")

    async def get_holdings(self) -> dict[str, Any]:
        """Derive holdings from Balance — non-USD assets with qty > 0.

        Returns normalized format:
        {"results": [{"symbol": "BTC-USD", "quantity": "0.5", ...}]}
        """
        balances = await self.get_account_balances()
        results = []

        for asset, qty_str in balances.items():
            qty = float(qty_str)
            if qty <= 0:
                continue
            # Skip fiat currencies
            from .symbols import _normalize_asset
            std_name = _normalize_asset(asset)
            if std_name in ("USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF"):
                continue

            results.append(
                {
                    "asset": std_name,
                    "symbol": f"{std_name}-USD",
                    "quantity": qty_str,
                    "quantity_float": qty,
                }
            )

        return {"results": results}

    async def get_open_orders(self) -> dict[str, Any]:
        """POST /0/private/OpenOrders"""
        result = await self._private_request("/0/private/OpenOrders")
        return result.get("open", {})

    async def get_order(self, order_id: str) -> dict[str, Any]:
        """POST /0/private/QueryOrders — query a specific order.

        Returns normalized format compatible with downstream consumers.
        """
        result = await self._private_request(
            "/0/private/QueryOrders", {"txid": order_id}
        )

        if order_id in result:
            order = result[order_id]
            descr = order.get("descr", {})
            status = order.get("status", "unknown")
            return {
                "id": order_id,
                "status": self._normalize_order_status(status),
                "symbol": from_kraken(descr.get("pair", "")),
                "side": descr.get("type", ""),
                "order_type": descr.get("ordertype", ""),
                "price": descr.get("price", "0"),
                "volume": order.get("vol", "0"),
                "volume_executed": order.get("vol_exec", "0"),
                "cost": order.get("cost", "0"),
                "fee": order.get("fee", "0"),
                "avg_price": order.get("price", "0"),
                "created_at": order.get("opentm", 0),
                "closed_at": order.get("closetm", 0),
                "raw": order,
            }

        return {"id": order_id, "status": "not_found", "raw": result}

    async def get_order_fills(self, order_id: str) -> dict[str, Any]:
        """POST /0/private/TradesHistory filtered by order.

        Returns: {"results": [{"fill_id": ..., "price": ..., "qty": ..., "fee": ...}]}
        """
        # Kraken doesn't have a direct "fills by order" endpoint.
        # We query TradesHistory and filter by ordertxid.
        result = await self._private_request(
            "/0/private/TradesHistory", {"type": "all"}
        )

        trades = result.get("trades", {})
        fills = []
        for trade_id, trade in trades.items():
            if trade.get("ordertxid") == order_id:
                fills.append(
                    {
                        "fill_id": trade_id,
                        "order_id": order_id,
                        "symbol": from_kraken(trade.get("pair", "")),
                        "side": trade.get("type", ""),
                        "price": trade.get("price", "0"),
                        "qty": trade.get("vol", "0"),
                        "fee": trade.get("fee", "0"),
                        "fee_currency": "USD",
                        "executed_at": trade.get("time", 0),
                        "cost": trade.get("cost", "0"),
                    }
                )

        return {"results": fills}

    async def get_recent_trades(self) -> dict[str, Any]:
        """POST /0/private/TradesHistory — get recent fills.

        Returns: {"results": [...], "count": N}
        """
        result = await self._private_request(
            "/0/private/TradesHistory", {"type": "all"}
        )

        trades = result.get("trades", {})
        fills = []
        for trade_id, trade in trades.items():
            fills.append(
                {
                    "fill_id": trade_id,
                    "order_id": trade.get("ordertxid", ""),
                    "symbol": from_kraken(trade.get("pair", "")),
                    "side": trade.get("type", ""),
                    "price": trade.get("price", "0"),
                    "qty": trade.get("vol", "0"),
                    "fee": trade.get("fee", "0"),
                    "cost": trade.get("cost", "0"),
                    "executed_at": trade.get("time", 0),
                }
            )

        return {"results": fills, "count": result.get("count", len(fills))}

    async def place_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        client_order_id: str = "",
        qty: Optional[float] = None,
        notional: Optional[float] = None,
        limit_price: Optional[float] = None,
    ) -> dict[str, Any]:
        """POST /0/private/AddOrder — place an order.

        Kraken requires volume (qty), not notional.
        If notional is provided and qty is not, we compute qty from limit_price.
        """
        kraken_pair = to_kraken(symbol)

        # Resolve quantity
        if qty is None and notional is not None:
            if limit_price and limit_price > 0:
                qty = notional / limit_price
            else:
                # Need current price to compute qty from notional
                ticker = await self.get_best_bid_ask(symbol)
                results = ticker.get("results", [])
                if results:
                    price = float(results[0]["ask_price"]) if side == "buy" else float(results[0]["bid_price"])
                    if price > 0:
                        qty = notional / price

        if qty is None or qty <= 0:
            raise ValueError(f"Cannot determine order quantity for {symbol}")

        data: dict[str, Any] = {
            "pair": kraken_pair,
            "type": side.lower(),  # "buy" or "sell"
            "ordertype": self._normalize_order_type(order_type),
            "volume": f"{qty:.10f}".rstrip("0").rstrip("."),
        }

        if limit_price is not None and order_type.lower() != "market":
            data["price"] = f"{limit_price:.10f}".rstrip("0").rstrip(".")

        if client_order_id:
            data["userref"] = abs(hash(client_order_id)) % (2**31)
            data["cl_ord_id"] = client_order_id[:50]  # Kraken max 50 chars

        # Validate mode
        data["validate"] = False  # Set to True for dry-run/paper mode

        result = await self._private_request("/0/private/AddOrder", data)

        order_ids = result.get("txid", [])
        order_id = order_ids[0] if order_ids else ""

        logger.info(
            "Order placed: %s %s %s qty=%.8f%s → %s",
            side.upper(),
            symbol,
            order_type,
            qty,
            f" @ {limit_price}" if limit_price else "",
            order_id,
        )

        return {
            "id": order_id,
            "status": "submitted",
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "qty": qty,
            "limit_price": limit_price,
            "client_order_id": client_order_id,
            "raw_response": result,
        }

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        """POST /0/private/CancelOrder"""
        result = await self._private_request(
            "/0/private/CancelOrder", {"txid": order_id}
        )
        logger.info("Order cancelled: %s (count=%s)", order_id, result.get("count", 0))
        return result

    async def get_ws_token(self) -> str:
        """POST /0/private/GetWebSocketsToken — get auth token for private WS."""
        result = await self._private_request("/0/private/GetWebSocketsToken")
        token = result.get("token", "")
        if not token:
            raise KrakenAPIError(["No WebSocket token received"])
        return token

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _normalize_order_status(kraken_status: str) -> str:
        """Map Kraken order status to our internal status."""
        mapping = {
            "pending": "submitted",
            "open": "submitted",
            "closed": "filled",
            "canceled": "canceled",
            "expired": "expired",
        }
        return mapping.get(kraken_status, kraken_status)

    @staticmethod
    def _normalize_order_type(order_type: str) -> str:
        """Map our order types to Kraken's."""
        mapping = {
            "market": "market",
            "limit": "limit",
            "stop": "stop-loss",
            "stop_limit": "stop-loss-limit",
        }
        return mapping.get(order_type.lower(), order_type.lower())


class KrakenAPIError(Exception):
    """Raised when Kraken API returns an error."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Kraken API error: {', '.join(errors)}")
