"""Paper broker — simulates order fills for paper trading mode.

Market orders: immediate fill at ask+slippage (buy) or bid-slippage (sell).
Limit orders: fill when price crosses limit, or stay pending (for reposition testing).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .price_cache import PriceCache


class PaperBroker:
    """Simulates a broker for paper trading. Implements the OrderBroker protocol."""

    def __init__(self, price_cache: PriceCache, slippage_bps: float = 10.0):
        self.price_cache = price_cache
        self.slippage_bps = slippage_bps
        self._orders: dict[str, dict[str, Any]] = {}

    async def place_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        client_order_id: str,
        notional: float | None = None,
        qty: float | None = None,
        limit_price: float | None = None,
    ) -> dict[str, Any]:
        """Place a simulated order."""
        order_id = f"paper-{uuid.uuid4()}"
        snap = self.price_cache.snapshot(symbol)
        bid = snap.get("bid", 0)
        ask = snap.get("ask", snap.get("mid", 0))
        mid = snap.get("mid", 0)

        if order_type == "market":
            # Immediate fill with slippage
            slippage_mult = self.slippage_bps / 10_000
            if side == "buy":
                fill_price = ask * (1 + slippage_mult) if ask > 0 else mid
            else:
                fill_price = bid * (1 - slippage_mult) if bid > 0 else mid

            fill_qty = qty or (notional / fill_price if fill_price > 0 and notional else 0)
            status = "filled"
        else:
            # Limit order: check if price already crosses limit
            fill_price = limit_price or mid
            fill_qty = qty or (notional / fill_price if fill_price > 0 and notional else 0)

            if side == "buy" and limit_price and ask > 0 and ask <= limit_price:
                status = "filled"
                fill_price = ask  # fill at ask (better than limit)
            elif side == "sell" and limit_price and bid > 0 and bid >= limit_price:
                status = "filled"
                fill_price = bid  # fill at bid
            else:
                status = "submitted"

        order = {
            "id": order_id,
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "qty": fill_qty,
            "notional": notional,
            "limit_price": limit_price,
            "status": status,
            "fill_price": fill_price if status == "filled" else None,
            "filled_at": datetime.now(timezone.utc).isoformat() if status == "filled" else None,
        }
        self._orders[order_id] = order
        return order

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel a pending order."""
        order = self._orders.get(order_id, {})
        if order.get("status") in ("submitted", "working", "partially_filled"):
            order["status"] = "canceled"
        return order

    async def get_order(self, order_id: str) -> dict[str, Any]:
        """Get current order state. For limit orders, check if price has crossed."""
        order = self._orders.get(order_id, {"status": "not_found"})

        # Check limit orders for fill conditions
        if order.get("status") in ("submitted", "working") and order.get("order_type") == "limit":
            symbol = order.get("symbol", "")
            limit_price = order.get("limit_price")
            side = order.get("side")
            snap = self.price_cache.snapshot(symbol)
            bid = snap.get("bid", 0)
            ask = snap.get("ask", 0)

            if side == "buy" and limit_price and ask > 0 and ask <= limit_price:
                order["status"] = "filled"
                order["fill_price"] = ask
                order["filled_at"] = datetime.now(timezone.utc).isoformat()
            elif side == "sell" and limit_price and bid > 0 and bid >= limit_price:
                order["status"] = "filled"
                order["fill_price"] = bid
                order["filled_at"] = datetime.now(timezone.utc).isoformat()

        return order

    async def get_order_fills(self, order_id: str) -> dict[str, Any]:
        """Get fills for a filled order."""
        order = self._orders.get(order_id, {})
        if order.get("status") == "filled":
            return {
                "results": [
                    {
                        "id": f"paper-fill-{uuid.uuid4()}",
                        "quantity": order.get("qty", 0),
                        "price": order.get("fill_price", 0),
                        "fee": (order.get("notional", 0) or 0) * 0.001,
                        "executed_at": order.get("filled_at"),
                    }
                ]
            }
        return {"results": []}
