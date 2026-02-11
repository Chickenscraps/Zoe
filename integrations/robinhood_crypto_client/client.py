from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

try:
    from nacl.signing import SigningKey
except Exception:  # pragma: no cover
    SigningKey = None


REDACTED_HEADERS = {"x-api-key", "x-signature", "authorization"}


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
    timeout_seconds: int = 15
    max_retries: int = 4

    @classmethod
    def from_env(cls) -> "RobinhoodCryptoConfig":
        return cls(
            api_key=os.getenv("RH_CRYPTO_API_KEY", ""),
            private_key_seed=os.getenv("RH_CRYPTO_PRIVATE_KEY_SEED", ""),
            base_url=os.getenv("RH_CRYPTO_BASE_URL", "https://trading.robinhood.com"),
        )


class RobinhoodCryptoClient:
    def __init__(self, config: RobinhoodCryptoConfig):
        if SigningKey is None:
            raise RuntimeError("PyNaCl required for Ed25519 signing (pip install pynacl)")
        if not config.api_key or not config.private_key_seed:
            raise RuntimeError("Missing RH_CRYPTO_API_KEY or RH_CRYPTO_PRIVATE_KEY_SEED")
        self.config = config
        seed = bytes.fromhex(config.private_key_seed)
        self._signing_key = SigningKey(seed)

    def _sign(self, timestamp: str, method: str, path: str, body: str) -> str:
        content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        signing_input = f"{timestamp}.{method.upper()}.{path}.{content_hash}".encode("utf-8")
        signature = self._signing_key.sign(signing_input).signature
        return base64.b64encode(signature).decode("utf-8")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = _stable_json(payload)
        body_bytes = body.encode("utf-8")
        timestamp = datetime.now(timezone.utc).isoformat()
        signature = self._sign(timestamp, method, path, body)

        headers = {
            "content-type": "application/json",
            "x-api-key": self.config.api_key,
            "x-timestamp": timestamp,
            "x-signature": signature,
        }
        url = f"{self.config.base_url.rstrip('/')}{path}"
        req = urllib.request.Request(url, data=body_bytes if method != "GET" else None, method=method, headers=headers)

        retries = 0
        while True:
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8") or "{}")
            except urllib.error.HTTPError as err:
                is_retryable = err.code in (429, 500, 502, 503, 504)
                if method == "POST" and not (payload or {}).get("client_order_id"):
                    is_retryable = False
                if retries >= self.config.max_retries or not is_retryable:
                    body_text = err.read().decode("utf-8", errors="ignore")
                    raise RuntimeError(f"Robinhood API error ({err.code}): {body_text[:500]}")
            except urllib.error.URLError as err:
                if retries >= self.config.max_retries:
                    raise RuntimeError(f"Network error: {err}")
            retries += 1
            time.sleep(min(2**retries, 10))

    def get_account_balances(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/crypto/trading/accounts/")

    def get_holdings(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/crypto/trading/holdings/")

    def place_order(self, *, symbol: str, side: str, order_type: str, client_order_id: str, notional: float | None = None, qty: float | None = None, limit_price: float | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "client_order_id": client_order_id,
        }
        if notional is not None:
            payload["notional"] = str(notional)
        if qty is not None:
            payload["quantity"] = str(qty)
        if limit_price is not None:
            payload["limit_price"] = str(limit_price)
        return self._request("POST", "/api/v1/crypto/trading/orders/", payload=payload)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/crypto/trading/orders/{order_id}/")

    def get_order_fills(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/crypto/trading/orders/{order_id}/fills/")


__all__ = [
    "RobinhoodCryptoClient",
    "RobinhoodCryptoConfig",
    "_stable_json",
    "_sanitize",
]
