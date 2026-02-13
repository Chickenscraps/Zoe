from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class Broker(ABC):
    @abstractmethod
    async def get_cash(self) -> float: ...

    @abstractmethod
    async def get_positions(self) -> Dict[str, float]: ...

    @abstractmethod
    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Dict[str, Any]: ...


class KrakenBroker(Broker):
    """Broker adapter for Kraken exchange."""

    def __init__(self, client: Any):
        self.client = client  # KrakenClient instance

    async def get_cash(self) -> float:
        balances = await self.client.get_account_balances()
        for key in ("ZUSD", "USD", "USDT"):
            if key in balances:
                val = float(balances[key])
                if val > 0:
                    return val
        return 0.0

    async def get_positions(self) -> Dict[str, float]:
        holdings_resp = await self.client.get_holdings()
        items = holdings_resp.get("results", [])
        return {
            item["symbol"]: float(item.get("quantity", 0.0))
            for item in items
            if float(item.get("quantity", 0.0)) > 0
        }

    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Dict[str, Any]:
        import uuid
        client_oid = f"zoe-kraken-{uuid.uuid4()}"
        return await self.client.place_order(
            symbol=symbol,
            side=side,
            order_type="limit",
            client_order_id=client_oid,
            qty=qty,
            limit_price=limit_price,
        )
