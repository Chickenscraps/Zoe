from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict

from integrations.robinhood_crypto_client import RobinhoodCryptoClient


class Broker(ABC):
    """Exchange-agnostic broker interface.

    Core methods (required):
      - get_cash, get_positions, place_order

    Extended methods (optional, with default no-op implementations
    so existing subclasses don't break):
      - cancel_order, get_open_orders, get_fills, get_balances
    """

    @abstractmethod
    async def get_cash(self) -> float: ...

    @abstractmethod
    async def get_positions(self) -> Dict[str, float]: ...

    @abstractmethod
    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float,
                          *, order_type: str = "limit", client_order_id: str | None = None) -> Dict[str, Any]: ...

    # ── Extended interface (added for Kraken; backward-compatible defaults) ──

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True if cancelled."""
        raise NotImplementedError(f"{type(self).__name__} does not support cancel_order")

    async def get_open_orders(self) -> list[Dict[str, Any]]:
        """List currently open orders."""
        return []

    async def get_fills(self, order_id: str) -> list[Dict[str, Any]]:
        """Get fills for a specific order."""
        return []

    async def get_balances(self) -> Dict[str, float]:
        """Get all asset balances (multi-asset). Default: {"USD": get_cash()}."""
        cash = await self.get_cash()
        return {"USD": cash}


class RobinhoodBroker(Broker):
    def __init__(self, client: RobinhoodCryptoClient):
        self.client = client

    async def get_cash(self) -> float:
        balances = await self.client.get_account_balances()
        return float(balances.get("cash_available", 0.0))

    async def get_positions(self) -> Dict[str, float]:
        holdings_resp = await self.client.get_holdings()
        items = holdings_resp.get("results", [])
        return {
            item["symbol"]: float(item.get("quantity", 0.0))
            for item in items
            if float(item.get("quantity", 0.0)) > 0
        }

    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float,
                          *, order_type: str = "limit", client_order_id: str | None = None) -> Dict[str, Any]:
        client_oid = client_order_id or f"zoe-prod-{uuid.uuid4()}"
        return await self.client.place_order(
            symbol=symbol,
            side=side,
            order_type="limit",
            client_order_id=client_oid,
            qty=qty,
            limit_price=limit_price
        )


class PaperBroker(Broker):
    """Simulates trades with Kraken-like fees.

    Fee model (matching Kraken base tier):
      - Market orders (taker): 0.40%
      - Limit orders (maker):  0.25%
    Slippage: 0.05% adverse (buy at ask + slippage, sell at bid - slippage).
    """

    TAKER_FEE_PCT = 0.0040   # 0.40%
    MAKER_FEE_PCT = 0.0025   # 0.25%
    SLIPPAGE_PCT = 0.0005    # 0.05%

    def __init__(self, market_data_provider: Any, repo: Any, starting_cash: float = 2000.0):
        self.mdp = market_data_provider
        self.repo = repo
        self._cash = starting_cash
        self._positions: Dict[str, float] = {}

    async def get_cash(self) -> float:
        return self._cash

    async def get_positions(self) -> Dict[str, float]:
        return dict(self._positions)

    async def get_balances(self) -> Dict[str, float]:
        balances: Dict[str, float] = {"USD": self._cash}
        for sym, qty in self._positions.items():
            if qty > 0:
                balances[sym] = qty
        return balances

    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float,
                          *, order_type: str = "limit", client_order_id: str | None = None) -> Dict[str, Any]:
        current_price = await self.mdp.get_current_price(symbol)

        # Determine fee rate based on order type
        fee_pct = self.TAKER_FEE_PCT if order_type == "market" else self.MAKER_FEE_PCT

        # Fill simulation
        filled = False
        avg_price = 0.0

        if side == "buy":
            if order_type == "market" or limit_price >= current_price:
                filled = True
                avg_price = current_price * (1 + self.SLIPPAGE_PCT)
        else:  # sell
            if order_type == "market" or limit_price <= current_price:
                filled = True
                avg_price = current_price * (1 - self.SLIPPAGE_PCT)

        order_id = client_order_id or str(uuid.uuid4())
        fee = round(qty * avg_price * fee_pct, 8) if filled else 0.0

        status = "filled" if filled else "open"
        order: Dict[str, Any] = {
            "id": order_id,
            "client_order_id": order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "type": order_type,
            "limit_price": limit_price,
            "status": status,
            "filled_qty": qty if filled else 0,
            "avg_price": avg_price,
            "fee": fee,
            "fee_currency": "USD",
        }

        if filled:
            cost = qty * avg_price
            if side == "buy":
                total_cost = cost + fee
                if self._cash >= total_cost:
                    self._cash -= total_cost
                    self._positions[symbol] = self._positions.get(symbol, 0.0) + qty
                else:
                    order["status"] = "rejected"
                    order["reject_reason"] = "Insufficient funds"
                    return order
            else:
                if self._positions.get(symbol, 0.0) >= qty:
                    self._cash += cost - fee
                    self._positions[symbol] -= qty
                    if self._positions[symbol] <= 0:
                        del self._positions[symbol]
                else:
                    order["status"] = "rejected"
                    order["reject_reason"] = "Insufficient position"
                    return order

            # Log to DB
            await self.repo.insert_order(order)
            await self.repo.upsert_fill({
                "order_id": order_id,
                "fill_id": f"paper-fill-{uuid.uuid4()}",
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": avg_price,
                "fee": fee,
                "fee_currency": "USD",
                "executed_at": datetime.now(timezone.utc).isoformat()
            })

        return order

    async def cancel_order(self, order_id: str) -> bool:
        # Paper broker: always succeeds (orders are instant-fill or nothing)
        return True
