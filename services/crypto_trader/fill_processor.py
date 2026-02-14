"""Fill processor — handles incoming execution events from Kraken WS.

Responsibilities:
  1. Parse execution messages (order status + trade fills)
  2. Upsert fills to crypto_fills (idempotent on fill_id)
  3. Update positions table (weighted average cost)
  4. Record fees in fee_ledger
  5. Update order intent status

Average cost position tracking:
  - Buy: new_avg = (old_qty * old_avg + fill_qty * fill_price) / (old_qty + fill_qty)
  - Sell: realized_pnl = (fill_price - avg_cost) * fill_qty - fee
           Reduce qty, avg_cost stays the same.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class FillProcessor:
    """Processes execution events and updates positions/fees."""

    def __init__(self, repository: Any, mode: str = "paper"):
        self.repo = repository
        self.mode = mode

    async def handle_execution(self, data: dict[str, Any]) -> None:
        """Process a Kraken WS v2 executions channel message.

        Message types:
          - snapshot: initial state on subscribe (snap_orders/snap_trades)
          - update: real-time order/trade events

        Each message contains a `data` array of execution entries.
        """
        msg_type = data.get("type", "")
        entries = data.get("data", [])

        for entry in entries if isinstance(entries, list) else [entries]:
            exec_type = entry.get("exec_type", "")
            if exec_type == "trade":
                await self._process_fill(entry)
            elif exec_type in ("new", "pending_new"):
                await self._process_order_new(entry)
            elif exec_type in ("canceled", "expired"):
                await self._process_order_cancel(entry)
            elif exec_type == "filled":
                await self._process_order_filled(entry)

    async def _process_fill(self, entry: dict[str, Any]) -> None:
        """Process a trade fill event."""
        fill_id = entry.get("trade_id", entry.get("exec_id", ""))
        order_id = entry.get("order_id", "")
        symbol = entry.get("symbol", "")
        side = entry.get("side", "")
        qty = float(entry.get("last_qty", entry.get("qty", 0)))
        price = float(entry.get("last_price", entry.get("avg_price", 0)))
        fee = float(entry.get("fee_paid", entry.get("fee", 0)))
        fee_currency = entry.get("fee_currency", "USD")

        if not fill_id or qty <= 0:
            return

        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Upsert fill (idempotent on fill_id)
        fill_row = {
            "order_id": order_id,
            "fill_id": fill_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "fee": fee,
            "fee_currency": fee_currency,
            "executed_at": entry.get("timestamp", now_iso),
            "mode": self.mode,
        }
        self.repo.upsert_fill(fill_row)

        # 2. Update position (avg cost method)
        self._update_position(symbol, side, qty, price, fee)

        # 3. Record fee in ledger
        fee_usd = fee  # assuming USD-quoted; convert if needed later
        self.repo.insert_fee_ledger({
            "fill_id": fill_id,
            "symbol": symbol,
            "fee": fee,
            "fee_currency": fee_currency,
            "fee_usd": fee_usd,
            "mode": self.mode,
        })

        logger.info(
            "Fill processed: %s %s %s qty=%.8f price=%.4f fee=%.6f %s",
            fill_id, side, symbol, qty, price, fee, fee_currency,
        )

    def _update_position(self, symbol: str, side: str, qty: float, price: float, fee: float) -> None:
        """Update position using weighted average cost method."""
        pos = self.repo.get_position(symbol, self.mode)
        old_qty = float(pos.get("qty", 0)) if pos else 0.0
        old_avg = float(pos.get("avg_cost", 0)) if pos else 0.0

        now_iso = datetime.now(timezone.utc).isoformat()

        if side == "buy":
            # Average cost: weighted average of old position and new fill
            # Include fee in cost basis for buys
            new_qty = old_qty + qty
            if new_qty > 0:
                new_avg = (old_qty * old_avg + qty * price + fee) / new_qty
            else:
                new_avg = price
            self.repo.upsert_position({
                "symbol": symbol,
                "qty": new_qty,
                "avg_cost": round(new_avg, 8),
                "mode": self.mode,
                "updated_at": now_iso,
            })

        elif side == "sell":
            # Sell: reduce qty, avg_cost stays. Realized P&L computed externally.
            new_qty = max(0.0, old_qty - qty)
            new_avg = old_avg if new_qty > 0 else 0.0
            self.repo.upsert_position({
                "symbol": symbol,
                "qty": new_qty,
                "avg_cost": round(new_avg, 8),
                "mode": self.mode,
                "updated_at": now_iso,
            })

    async def _process_order_new(self, entry: dict[str, Any]) -> None:
        """Handle new order acknowledgment."""
        order_id = entry.get("order_id", "")
        cl_oid = entry.get("cl_ord_id", "")
        if order_id:
            # Update crypto_orders status
            self.repo.update_order_status(order_id, "submitted", entry)
        logger.info("Order new: %s cl_oid=%s", order_id, cl_oid)

    async def _process_order_cancel(self, entry: dict[str, Any]) -> None:
        """Handle order cancellation."""
        order_id = entry.get("order_id", "")
        if order_id:
            self.repo.update_order_status(order_id, "canceled", entry)
        logger.info("Order canceled: %s", order_id)

    async def _process_order_filled(self, entry: dict[str, Any]) -> None:
        """Handle order fully filled event."""
        order_id = entry.get("order_id", "")
        if order_id:
            self.repo.update_order_status(order_id, "filled", entry)
        logger.info("Order filled: %s", order_id)

    def compute_realized_pnl(self, symbol: str, sell_qty: float, sell_price: float, fee: float) -> float:
        """Compute realized P&L for a sell using average cost method.

        realized = (sell_price - avg_cost) * qty - fee
        """
        pos = self.repo.get_position(symbol, self.mode)
        avg_cost = float(pos.get("avg_cost", 0)) if pos else 0.0
        return (sell_price - avg_cost) * sell_qty - fee
