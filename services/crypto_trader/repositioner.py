"""Repositioner — cancels stale limit orders that haven't filled.

Runs periodically to clean up unfilled limit orders beyond a configurable
timeout (default: 5 minutes / 300 seconds). This prevents capital from
being locked up in stale orders.

Can also be extended to replace (cancel + resubmit) orders at a better price.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .broker import Broker

logger = logging.getLogger(__name__)


class Repositioner:
    """Monitors open limit orders and cancels stale ones."""

    def __init__(
        self,
        broker: Broker,
        repository: Any,
        mode: str = "paper",
        timeout_s: float = 300.0,  # 5 minutes
    ):
        self.broker = broker
        self.repo = repository
        self.mode = mode
        self.timeout_s = timeout_s

    async def check_and_cancel_stale(self) -> list[str]:
        """Cancel open orders older than timeout_s.

        Returns list of cancelled order IDs.
        """
        open_orders = self.repo.list_open_orders(self.mode)
        now = time.time()
        cancelled: list[str] = []

        for order in open_orders:
            order_id = order.get("id", "")
            requested_at = order.get("requested_at", "")
            order_type = order.get("order_type", "")

            # Only cancel limit orders (market orders should fill immediately)
            if order_type != "limit":
                continue

            # Parse timestamp and check age
            if not requested_at:
                continue

            try:
                from datetime import datetime, timezone
                if isinstance(requested_at, str):
                    # Handle ISO format with timezone
                    ts = datetime.fromisoformat(requested_at.replace("Z", "+00:00"))
                    order_age_s = (datetime.now(timezone.utc) - ts).total_seconds()
                else:
                    continue
            except (ValueError, TypeError):
                continue

            if order_age_s > self.timeout_s:
                try:
                    success = await self.broker.cancel_order(order_id)
                    if success:
                        self.repo.update_order_status(order_id, "canceled", {
                            "cancel_reason": "repositioner_timeout",
                            "age_seconds": order_age_s,
                        })
                        # Also update intent if linked
                        intent_id = order.get("intent_id")
                        if intent_id:
                            self.repo.update_order_intent_status(
                                intent_id, "cancelled",
                                reason="repositioner_timeout",
                            )
                        cancelled.append(order_id)
                        logger.info(
                            "Repositioner cancelled stale order %s (age=%.0fs, timeout=%.0fs)",
                            order_id, order_age_s, self.timeout_s,
                        )
                except Exception as e:
                    logger.error("Repositioner failed to cancel %s: %s", order_id, e)

        if cancelled:
            logger.info("Repositioner cancelled %d stale orders", len(cancelled))

        return cancelled
