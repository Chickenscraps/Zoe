"""KrakenBroker — Broker implementation backed by Kraken Spot REST API.

Translates the generic Broker interface into Kraken REST calls.
Handles symbol normalization (internal BTC-USD ↔ Kraken BTC/USD) and
maps Kraken's response structures to the dict format expected by
the trader service.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict

from .broker import Broker
from .kraken_client import KrakenRestClient, AssetPairInfo
from .symbol_map import to_kraken, to_internal, normalize_kraken_asset


class KrakenBroker(Broker):
    """Live broker implementation for Kraken Spot."""

    def __init__(self, client: KrakenRestClient):
        self.client = client
        # Cache of Kraken pair altnames keyed by friendly symbol ("BTC/USD" → "XBTUSD")
        self._pair_altnames: dict[str, str] = {}

    async def ensure_pair_cache(self) -> None:
        """Populate the pair altname cache if empty."""
        if self._pair_altnames:
            return
        pairs = await self.client.get_asset_pairs()
        for p in pairs:
            self._pair_altnames[p.symbol] = p.altname

    def _resolve_pair(self, internal_symbol: str) -> str:
        """Convert internal symbol to Kraken REST pair name.

        Kraken REST endpoints accept altnames (e.g. "XBTUSD") or wsnames.
        We prefer altname since it's the canonical REST key.
        Falls back to the slash-separated name if altname not cached.
        """
        kraken_sym = to_kraken(internal_symbol)  # "BTC/USD"
        return self._pair_altnames.get(kraken_sym, kraken_sym)

    # ── Core interface ──

    async def get_cash(self) -> float:
        balances = await self.client.get_balance()
        # Sum USD-like balances
        return sum(
            v for k, v in balances.items()
            if k in ("USD", "ZUSD", "USDC", "USDT")
        )

    async def get_positions(self) -> Dict[str, float]:
        balances = await self.client.get_balance()
        positions: Dict[str, float] = {}
        for asset, qty in balances.items():
            if asset in ("USD", "ZUSD", "USDC", "USDT"):
                continue  # skip cash-like
            if qty > 0:
                positions[asset] = qty
        return positions

    async def get_balances(self) -> Dict[str, float]:
        return await self.client.get_balance()

    async def place_order(self, symbol: str, side: str, qty: float, limit_price: float,
                          *, order_type: str = "limit", client_order_id: str | None = None) -> Dict[str, Any]:
        await self.ensure_pair_cache()
        pair = self._resolve_pair(symbol)
        cl_oid = client_order_id or f"zoe-{symbol.lower()}-{uuid.uuid4()}"

        result = await self.client.add_order(
            pair=pair,
            side=side,
            order_type=order_type,
            volume=qty,
            price=limit_price if order_type == "limit" else None,
            client_order_id=cl_oid,
        )

        return {
            "id": result.order_id,
            "client_order_id": cl_oid,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "type": order_type,
            "limit_price": limit_price,
            "status": result.status,
            "description": result.description,
            "raw_response": result.raw,
        }

    # ── Extended interface ──

    async def cancel_order(self, order_id: str) -> bool:
        return await self.client.cancel_order(order_id)

    async def get_open_orders(self) -> list[Dict[str, Any]]:
        orders = await self.client.get_open_orders()
        return [
            {
                "id": o.order_id,
                "symbol": o.symbol,
                "side": o.side,
                "order_type": o.order_type,
                "price": o.price,
                "qty": o.qty,
                "filled_qty": o.filled_qty,
                "status": o.status,
                "client_order_id": o.client_order_id,
                "open_time": o.open_time,
            }
            for o in orders
        ]

    async def get_fills(self, order_id: str) -> list[Dict[str, Any]]:
        # Kraken doesn't have a per-order fills endpoint; use TradesHistory and filter
        trades = await self.client.get_trades_history()
        return [
            {
                "fill_id": t.trade_id,
                "order_id": t.order_id,
                "symbol": t.symbol,
                "side": t.side,
                "qty": t.qty,
                "price": t.price,
                "fee": t.fee,
                "fee_currency": t.fee_currency,
                "executed_at": t.timestamp,
            }
            for t in trades
            if t.order_id == order_id
        ]
