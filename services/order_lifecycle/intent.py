"""OrderIntent — persistent, idempotent order tracking with state machine.

State transitions:
    CREATED → SUBMITTED → ACKED → PARTIAL_FILL → FILLED
                               → CANCEL_REQUESTED → CANCELLED → REPLACED (new intent)
                               → REJECTED
                               → EXPIRED
                               → ERROR

Each intent has an idempotency_key to prevent duplicate submissions.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Valid state transitions
VALID_TRANSITIONS: dict[str, set[str]] = {
    "created": {"submitted", "error"},
    "submitted": {"acked", "filled", "partial_fill", "rejected", "error", "cancel_requested"},
    "acked": {"filled", "partial_fill", "cancel_requested", "expired", "error"},
    "partial_fill": {"filled", "cancel_requested", "error"},
    "cancel_requested": {"cancelled", "filled", "error"},
    "cancelled": {"replaced"},
    "replaced": set(),
    "filled": set(),
    "rejected": set(),
    "expired": set(),
    "error": {"submitted"},  # allow retry from error
}

TERMINAL_STATES = {"filled", "cancelled", "replaced", "rejected", "expired"}


@dataclass
class OrderIntent:
    """Persistent order intent."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str = ""
    symbol: str = ""
    side: str = ""  # "buy" | "sell"
    order_type: str = "limit"  # "limit" | "market"
    qty: float | None = None
    notional: float | None = None
    limit_price: float | None = None
    engine: str = ""  # "edge_factory" | "crypto_trader"
    mode: str = "paper"
    status: str = "created"
    broker_order_id: str | None = None
    fill_price: float | None = None
    fill_qty: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in VALID_TRANSITIONS.get(self.status, set())

    def transition(self, new_status: str) -> None:
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Invalid transition: {self.status} → {new_status} "
                f"(allowed: {VALID_TRANSITIONS.get(self.status, set())})"
            )
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)


class IntentManager:
    """Creates and manages OrderIntents in Supabase."""

    def __init__(self, supabase_client: Any):
        self._sb = supabase_client

    async def create_intent(
        self,
        symbol: str,
        side: str,
        order_type: str = "limit",
        qty: float | None = None,
        notional: float | None = None,
        limit_price: float | None = None,
        engine: str = "",
        mode: str = "paper",
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OrderIntent:
        """Create a new order intent. Idempotent on idempotency_key."""
        intent = OrderIntent(
            idempotency_key=idempotency_key or str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            notional=notional,
            limit_price=limit_price,
            engine=engine,
            mode=mode,
            metadata=metadata or {},
        )

        try:
            self._sb.table("order_intents").upsert({
                "id": intent.id,
                "idempotency_key": intent.idempotency_key,
                "symbol": intent.symbol,
                "side": intent.side,
                "order_type": intent.order_type,
                "qty": intent.qty,
                "notional": intent.notional,
                "limit_price": intent.limit_price,
                "engine": intent.engine,
                "mode": intent.mode,
                "status": intent.status,
                "metadata": intent.metadata,
            }, on_conflict="idempotency_key").execute()
        except Exception as e:
            logger.warning("Intent create failed: %s", e)

        return intent

    async def update_status(
        self,
        intent_id: str,
        new_status: str,
        broker_order_id: str | None = None,
        fill_price: float | None = None,
        fill_qty: float | None = None,
    ) -> None:
        """Update intent status with optional fill data."""
        update: dict[str, Any] = {
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if broker_order_id is not None:
            update["broker_order_id"] = broker_order_id
        if fill_price is not None:
            update["fill_price"] = fill_price
        if fill_qty is not None:
            update["fill_qty"] = fill_qty

        try:
            self._sb.table("order_intents").update(update).eq(
                "id", intent_id
            ).execute()
        except Exception as e:
            logger.warning("Intent update failed: %s", e)

    async def get_active_intents(self, mode: str) -> list[dict[str, Any]]:
        """Get all non-terminal intents."""
        try:
            resp = self._sb.table("order_intents").select("*").eq(
                "mode", mode
            ).not_.in_("status", list(TERMINAL_STATES)).execute()
            return resp.data or []
        except Exception as e:
            logger.warning("Intent query failed: %s", e)
            return []

    async def get_intent(self, intent_id: str) -> dict[str, Any] | None:
        """Get a single intent by ID."""
        try:
            resp = self._sb.table("order_intents").select("*").eq(
                "id", intent_id
            ).maybeSingle().execute()
            return resp.data
        except Exception as e:
            logger.warning("Intent fetch failed: %s", e)
            return None
