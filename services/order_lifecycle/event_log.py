"""Append-only order event log.

Every state change, fill, cancellation, or error gets an immutable event row.
This provides a complete audit trail for order lifecycle debugging.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class OrderEventLog:
    """Writes append-only events to the order_events table."""

    def __init__(self, supabase_client: Any):
        self._sb = supabase_client

    async def log_event(
        self,
        intent_id: str,
        event_type: str,
        broker_order_id: str | None = None,
        fill_price: float | None = None,
        fill_qty: float | None = None,
        fee: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Append an order event."""
        try:
            self._sb.table("order_events").insert({
                "id": str(uuid.uuid4()),
                "intent_id": intent_id,
                "event_type": event_type,
                "broker_order_id": broker_order_id,
                "fill_price": fill_price,
                "fill_qty": fill_qty,
                "fee": fee,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as e:
            logger.warning("Event log write failed: %s", e)

    async def get_events_for_intent(self, intent_id: str) -> list[dict[str, Any]]:
        """Get all events for an intent, ordered chronologically."""
        try:
            resp = self._sb.table("order_events").select("*").eq(
                "intent_id", intent_id
            ).order("created_at").execute()
            return resp.data or []
        except Exception as e:
            logger.warning("Event log read failed: %s", e)
            return []

    async def get_recent_events(
        self, mode: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get recent events across all intents."""
        try:
            query = self._sb.table("order_events").select(
                "*, order_intents!inner(symbol, side, mode)"
            ).order("created_at", desc=True).limit(limit)
            if mode:
                query = query.eq("order_intents.mode", mode)
            resp = query.execute()
            return resp.data or []
        except Exception as e:
            logger.warning("Recent events read failed: %s", e)
            return []
