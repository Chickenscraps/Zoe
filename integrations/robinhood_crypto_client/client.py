from __future__ import annotations

import asyncio
import base64
import json
import os
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp

try:
    from nacl.signing import SigningKey
except Exception:  # pragma: no cover
    SigningKey = None


REDACTED_HEADERS = {"x-api-key", "x-signature", "authorization"}

# ── Time-offset helpers (system clock is ~1 year ahead) ──────────────

# Exactly 365 days in seconds (2025→2026, non-leap).
_HARDCODED_YEAR_OFFSET = 365 * 86400  # 31 536 000

# NTP epoch starts at 1900-01-01; Unix epoch at 1970-01-01.
_NTP_EPOCH_DELTA = 2208988800

# Well-known NTP servers (IPs avoid DNS issues).
_NTP_SERVERS = [
    "pool.ntp.org",       # DNS-based pool (tried first)
    "time.google.com",    # Google public NTP
    "129.6.15.28",        # NIST (time-a-g.nist.gov)
    "132.163.97.1",       # NIST backup
]


def _ntp_query(server: str, timeout: float = 3.0) -> float | None:
    """Query a single NTP server via raw UDP. Returns Unix epoch or None."""
    try:
        # NTP v3 client request: 48 bytes, first byte = 0x1B (LI=0, VN=3, Mode=3)
        packet = b"\x1b" + 47 * b"\0"
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(packet, (server, 123))
        data, _ = sock.recvfrom(1024)
        sock.close()
        if len(data) < 48:
            return None
        # Transmit timestamp is at bytes 40-47 (seconds + fraction).
        ntp_seconds = struct.unpack("!I", data[40:44])[0]
        return ntp_seconds - _NTP_EPOCH_DELTA
    except Exception:
        return None


def get_time_offset() -> float:
    """Return the number of seconds to SUBTRACT from time.time() to get real UTC.

    Resolution order:
      1. RH_TIME_OFFSET env var  (manual override, e.g. "31536000")
      2. NTP query               (auto-detect)
      3. Hardcoded 1-year offset (bulletproof fallback)
    """
    # 1. Manual override
    env_offset = os.getenv("RH_TIME_OFFSET")
    if env_offset is not None:
        try:
            val = float(env_offset)
            print(f"[TIME] Offset from RH_TIME_OFFSET env: {val:.0f}s")
            return val
        except ValueError:
            pass

    # 2. NTP auto-detect
    for server in _NTP_SERVERS:
        real_ts = _ntp_query(server)
        if real_ts is not None:
            offset = time.time() - real_ts
            # Sanity check: offset should be > 30 000 000 (roughly ~1 year).
            # If it's near zero the system clock is fine and we don't need to adjust.
            if abs(offset) < 60:
                print(f"[TIME] NTP says clock is accurate (offset {offset:.1f}s) - no adjustment needed")
                return 0.0
            print(f"[TIME] NTP offset detected via {server}: {offset:.0f}s (~{offset/86400:.0f} days)")
            return offset

    # 3. Hardcoded fallback
    print(f"[TIME] NTP unreachable - using hardcoded 1-year offset ({_HARDCODED_YEAR_OFFSET}s)")
    return float(_HARDCODED_YEAR_OFFSET)


def _stable_json(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return ""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def _sanitize(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            k: ("[REDACTED]" if k.lower() in REDACTED_HEADERS else _sanitize(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_sanitize(v) for v in data]
    return data


@dataclass
class RobinhoodCryptoConfig:
    api_key: str
    private_key_seed: str
    base_url: str = "https://trading.robinhood.com"
    timeout_seconds: int = 20
    max_retries: int = 3
    # Rate Limiting
    rate_limit_burst: int = 50
    rate_limit_refill_per_sec: float = 2.0  # ~120/min

    @classmethod
    def from_env(cls) -> "RobinhoodCryptoConfig":
        return cls(
            api_key=os.getenv("RH_CRYPTO_API_KEY", ""),
            private_key_seed=os.getenv("RH_CRYPTO_PRIVATE_KEY_SEED", ""),
            base_url=os.getenv("RH_CRYPTO_BASE_URL", "https://trading.robinhood.com"),
        )


class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = float(capacity)
        self._tokens = float(capacity)
        self.refill_rate = refill_rate
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.last_refill = now
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
            
            if self._tokens < tokens:
                wait_time = (tokens - self._tokens) / self.refill_rate
                await asyncio.sleep(wait_time)
                self._tokens -= tokens
            else:
                self._tokens -= tokens


class RobinhoodCryptoClient:
    """Async Client with Ed25519 signing and Rate Limiting."""

    def __init__(self, config: RobinhoodCryptoConfig):
        if SigningKey is None:
            raise RuntimeError("PyNaCl required for Ed25519 signing (pip install pynacl)")
        if not config.api_key or not config.private_key_seed:
            raise RuntimeError("Missing RH_CRYPTO_API_KEY or RH_CRYPTO_PRIVATE_KEY_SEED")

        self.config = config
        seed = bytes.fromhex(config.private_key_seed)
        self._signing_key = SigningKey(seed)
        self._limiter = TokenBucket(config.rate_limit_burst, config.rate_limit_refill_per_sec)
        self._session: Optional[aiohttp.ClientSession] = None
        # Compute clock offset once at init (NTP → hardcoded fallback)
        self._time_offset = get_time_offset()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            )
        return self._session

    def _sign(self, timestamp: str, method: str, path: str, body: str) -> str:
        # Robinhood signing format: api_key + timestamp + path + METHOD + body
        # (concatenated, no separators)
        message = f"{self.config.api_key}{timestamp}{path}{method.upper()}{body}"
        signature = self._signing_key.sign(message.encode("utf-8")).signature
        return base64.b64encode(signature).decode("utf-8")

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        await self._limiter.acquire()

        session = await self._get_session()

        body = _stable_json(payload)

        # Correct timestamp: subtract the pre-computed offset so Robinhood
        # sees real-world UTC even though the local clock may be off.
        now_ts = time.time() - self._time_offset
        timestamp = str(int(now_ts))  # Unix epoch seconds as string
        
        signature = self._sign(timestamp, method, path, body)

        headers = {
            "content-type": "application/json",
            "x-api-key": self.config.api_key,
            "x-timestamp": timestamp,
            "x-signature": signature,
        }
        url = f"{self.config.base_url.rstrip('/')}{path}"
        
        retries = 0
        while True:
            try:
                async with session.request(method, url, data=body if method != "GET" else None, headers=headers) as resp:
                    if resp.status == 429:
                        # Rate limit hit - backoff
                        retry_after = float(resp.headers.get("Retry-After", 2.0))
                        print(f"[RH] Rate Limit (429). Sleeping {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                        
                    if resp.status >= 500:
                        resp.raise_for_status()
                    
                    if 200 <= resp.status < 300:
                        text = await resp.text()
                        return json.loads(text) if text else {}
                    
                    # 4xx errors
                    text = await resp.text()
                    raise RuntimeError(f"Robinhood API Error {resp.status}: {text[:200]}")
                    
            except aiohttp.ClientError as e:
                if retries >= self.config.max_retries:
                    raise RuntimeError(f"Network error after {retries} retries: {e}")
                retries += 1
                await asyncio.sleep(0.5 * (2 ** retries))
            except Exception as e:
                # Catch-all
                raise e

    async def get_account_balances(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/crypto/trading/accounts/")

    async def get_holdings(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/crypto/trading/holdings/")

    async def place_order(self, *, symbol: str, side: str, order_type: str, client_order_id: str, notional: float | None = None, qty: float | None = None, limit_price: float | None = None) -> dict[str, Any]:
        """Place a crypto order via RH API v1.

        The v1 API requires order configuration in a nested
        ``{type}_order_config`` object rather than flat fields.
        """
        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "client_order_id": client_order_id,
        }

        # Build the order-type-specific config object
        config_key = f"{order_type}_order_config"
        order_config: dict[str, Any] = {}

        # RH requires prices rounded to nearest $0.01
        rounded_price = f"{limit_price:.2f}" if limit_price is not None else None
        rounded_notional = f"{notional:.2f}" if notional is not None else None

        if order_type == "limit":
            if rounded_price is not None:
                order_config["limit_price"] = rounded_price
            order_config["time_in_force"] = "gtc"
            if rounded_notional is not None:
                order_config["quote_amount"] = rounded_notional
            elif qty is not None:
                order_config["asset_quantity"] = str(qty)
        elif order_type == "market":
            if qty is not None:
                order_config["asset_quantity"] = str(qty)
            elif rounded_notional is not None:
                order_config["quote_amount"] = rounded_notional
        else:
            # stop_limit / stop_loss — pass through for future use
            if rounded_price is not None:
                order_config["limit_price"] = rounded_price
            order_config["time_in_force"] = "gtc"
            if qty is not None:
                order_config["asset_quantity"] = str(qty)
            elif rounded_notional is not None:
                order_config["quote_amount"] = rounded_notional

        payload[config_key] = order_config
        return await self._request("POST", "/api/v1/crypto/trading/orders/", payload=payload)

    async def get_order(self, order_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/crypto/trading/orders/{order_id}/")

    async def get_order_fills(self, order_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/crypto/trading/orders/{order_id}/fills/")
    
    async def get_best_bid_ask(self, symbol: str) -> dict[str, Any]:
        """Get current best bid/ask for a single symbol."""
        return await self._request("GET", f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}")

    async def get_best_bid_ask_batch(self, symbols: list[str]) -> dict[str, Any]:
        """Get best bid/ask for multiple symbols in one call."""
        query = "&".join(f"symbol={s}" for s in symbols)
        return await self._request("GET", f"/api/v1/crypto/marketdata/best_bid_ask/?{query}")

    async def get_estimated_price(self, symbol: str, side: str = "both", quantities: list[float] | None = None) -> dict[str, Any]:
        """Get estimated prices at given quantities (order depth/slippage).

        Args:
            symbol: e.g. "BTC-USD"
            side: "bid", "ask", or "both"
            quantities: list of quantities to estimate price for
        """
        qtys = quantities or [1.0]
        qty_str = ",".join(f"{q:.8f}" for q in qtys)
        return await self._request(
            "GET",
            f"/api/v1/crypto/marketdata/estimated_price/?symbol={symbol}&side={side}&quantity={qty_str}",
        )

    async def get_trading_pairs(self, symbols: list[str] | None = None) -> dict[str, Any]:
        """Get trading pair info (min order size, tick size, status, etc.)."""
        if symbols:
            query = "&".join(f"symbol={s}" for s in symbols)
            return await self._request("GET", f"/api/v1/crypto/trading/trading_pairs/?{query}")
        return await self._request("GET", "/api/v1/crypto/trading/trading_pairs/")

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


__all__ = [
    "RobinhoodCryptoClient",
    "RobinhoodCryptoConfig",
    "_stable_json",
    "_sanitize",
]
