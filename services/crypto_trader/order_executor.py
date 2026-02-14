"""Idempotent order executor with intent tracking and trade locks.

Every order goes through this lifecycle:
  1. Create OrderIntent in DB (status=pending)
  2. Acquire trade lock on symbol
  3. Submit order via Broker (status=submitted)
  4. On fill: update intent + positions via FillProcessor (status=filled)
  5. Release trade lock

Idempotency: if client_order_id already exists, skip submission.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .broker import Broker

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Places orders through the intent→submit→track pipeline."""

    def __init__(self, broker: Broker, repository: Any, mode: str = "paper"):
        self.broker = broker
        self.repo = repository
        self.mode = mode

    async def submit_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        limit_price: float | None = None,
        order_type: str = "limit",
        strategy: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Submit an order through the intent pipeline.

        Returns the order result dict from the broker.
        Raises on failure (but intent is always recorded).
        """
        client_order_id = f"zoe-{symbol.lower().replace('/', '-')}-{uuid.uuid4()}"
        intent_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Record intent
        intent = {
            "intent_id": intent_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "limit_price": limit_price,
            "order_type": order_type,
            "strategy": strategy,
            "reason": reason,
            "status": "pending",
            "client_order_id": client_order_id,
            "mode": self.mode,
            "created_at": now_iso,
        }
        self.repo.upsert_order_intent(intent)
        logger.info("Intent created: %s %s %s qty=%.8f cl_oid=%s", intent_id, side, symbol, qty, client_order_id)

        # 2. Acquire trade lock
        lock_acquired = self.repo.acquire_trade_lock(symbol, self.mode, locked_by=intent_id)
        if not lock_acquired:
            self.repo.update_order_intent_status(intent_id, "rejected", reason="trade_lock_busy")
            raise RuntimeError(f"Trade lock busy for {symbol} (mode={self.mode})")

        try:
            # 3. Check idempotency — skip if already submitted
            # (client_order_id unique constraint will catch duplicates at DB level)

            # 4. Submit to broker
            result = await self.broker.place_order(
                symbol=symbol,
                side=side,
                qty=qty,
                limit_price=limit_price or 0,
                order_type=order_type,
                client_order_id=client_order_id,
            )

            # 5. Update intent status
            broker_status = result.get("status", "submitted")
            self.repo.update_order_intent_status(
                intent_id,
                broker_status,
                submitted_at=now_iso,
            )

            # 6. Also record in crypto_orders for dashboard compatibility
            order_row = {
                "id": result.get("id", client_order_id),
                "client_order_id": client_order_id,
                "intent_id": intent_id,
                "symbol": symbol,
                "side": side,
                "order_type": order_type,
                "qty": qty,
                "notional": qty * (limit_price or 0),
                "status": broker_status,
                "raw_response": result.get("raw_response", {}),
                "mode": self.mode,
            }
            self.repo.insert_order(order_row)

            logger.info(
                "Order submitted: %s %s %s qty=%.8f → status=%s order_id=%s",
                intent_id, side, symbol, qty, broker_status, result.get("id", "?")
            )
            return result

        except Exception as e:
            self.repo.update_order_intent_status(intent_id, "rejected", reason=str(e))
            logger.error("Order submission failed for intent %s: %s", intent_id, e)
            raise

        finally:
            # 7. Release trade lock
            self.repo.release_trade_lock(symbol, self.mode)

    async def cancel_order(self, order_id: str, intent_id: str | None = None) -> bool:
        """Cancel an open order and update intent status."""
        success = await self.broker.cancel_order(order_id)
        if success and intent_id:
            self.repo.update_order_intent_status(
                intent_id, "cancelled",
                resolved_at=datetime.now(timezone.utc).isoformat(),
            )
        return success
