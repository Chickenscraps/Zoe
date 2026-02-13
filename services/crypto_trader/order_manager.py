"""Unified Order Manager — tracks orders from intent → fill/cancel with repositioning.

State machine:
  NEW → SUBMITTED → WORKING → (PARTIAL)* → FILLED
  WORKING/PARTIAL → CANCEL_PENDING → CANCELLED → REPLACED (new order)
  Any → REJECTED/FAILED (terminal)

Each order belongs to an intent_group_id. Replacement orders share the same intent
but increment replace_count and link via parent_order_id.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .reposition_policy import RepositionPolicy, RepositionDecision


# ── Terminal states ──
TERMINAL_STATES = frozenset({"filled", "canceled", "cancelled", "rejected", "failed"})
OPEN_STATES = frozenset({"new", "submitted", "working", "partially_filled"})
CANCEL_PENDING_STATES = frozenset({"cancel_pending"})


@dataclass
class ManagedOrder:
    """In-memory representation of an order being managed."""
    order_id: str
    intent_group_id: str
    symbol: str
    side: str
    notional: float
    qty: float | None
    limit_price: float | None
    status: str
    replace_count: int
    parent_order_id: str | None
    submitted_at: float  # monotonic time
    ttl_seconds: int
    filled_qty: float = 0.0
    remaining_qty: float | None = None


class OrderBroker(Protocol):
    """Minimal broker interface needed by OrderManager."""
    async def place_order(self, *, symbol: str, side: str, order_type: str,
                          client_order_id: str, notional: float | None = None,
                          qty: float | None = None, limit_price: float | None = None) -> dict[str, Any]: ...
    async def cancel_order(self, order_id: str) -> dict[str, Any]: ...
    async def get_order(self, order_id: str) -> dict[str, Any]: ...


class OrderRepository(Protocol):
    """Repository methods needed by OrderManager."""
    def insert_order(self, order: dict[str, Any]) -> None: ...
    def update_order_status(self, order_id: str, status: str, raw: dict[str, Any]) -> None: ...
    def list_open_orders(self, mode: str) -> list[dict[str, Any]]: ...
    def upsert_fill(self, fill: dict[str, Any]) -> None: ...


class OrderManager:
    """Manages order lifecycle with TTL-based repositioning."""

    def __init__(
        self,
        broker: OrderBroker,
        repo: OrderRepository,
        mode: str,
        policy: RepositionPolicy | None = None,
        on_event: Any | None = None,
    ):
        self.broker = broker
        self.repo = repo
        self.mode = mode
        self.policy = policy or RepositionPolicy()
        self._on_event = on_event  # callback for order_events persistence
        self._orders: dict[str, ManagedOrder] = {}  # order_id -> ManagedOrder
        self._intents: dict[str, dict[str, Any]] = {}  # intent_group_id -> intent data

    async def submit_intent(
        self,
        *,
        symbol: str,
        side: str,
        notional: float,
        purpose: str = "entry",
        strategy: str | None = None,
        confidence: float | None = None,
        order_type: str = "market",
        limit_price: float | None = None,
        qty: float | None = None,
    ) -> str:
        """Create an intent and submit the first order. Returns intent_group_id."""
        intent_id = str(uuid.uuid4())
        ttl = self.policy.ttl_for(side, purpose)

        # Persist intent
        self._intents[intent_id] = {
            "id": intent_id,
            "symbol": symbol,
            "side": side,
            "purpose": purpose,
            "target_notional": notional,
            "signal_confidence": confidence,
            "strategy": strategy,
            "status": "active",
            "max_reprices": self.policy.max_reprice_attempts,
            "mode": self.mode,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Submit first order
        order_id = await self._submit_order(
            intent_id=intent_id,
            symbol=symbol,
            side=side,
            notional=notional,
            qty=qty,
            order_type=order_type,
            limit_price=limit_price,
            replace_count=0,
            parent_order_id=None,
            ttl=ttl,
        )

        return intent_id

    async def _submit_order(
        self,
        *,
        intent_id: str,
        symbol: str,
        side: str,
        notional: float,
        qty: float | None,
        order_type: str,
        limit_price: float | None,
        replace_count: int,
        parent_order_id: str | None,
        ttl: int,
    ) -> str:
        """Submit a single order to the broker."""
        client_order_id = f"zoe-{symbol.lower()}-{intent_id[:8]}-r{replace_count}"
        idempotency_key = f"{intent_id}-{replace_count}"

        order_resp = await self.broker.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            client_order_id=client_order_id,
            notional=notional,
            qty=qty,
            limit_price=limit_price,
        )

        order_id = order_resp.get("id", client_order_id)
        status = order_resp.get("status", "submitted")

        # Persist to DB
        self.repo.insert_order({
            "id": order_id,
            "client_order_id": client_order_id,
            "idempotency_key": idempotency_key,
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "qty": qty,
            "notional": notional,
            "limit_price": limit_price,
            "status": status,
            "intent_group_id": intent_id,
            "replace_count": replace_count,
            "parent_order_id": parent_order_id,
            "ttl_seconds": ttl,
            "next_action_at": datetime.fromtimestamp(
                time.time() + ttl, tz=timezone.utc
            ).isoformat(),
            "raw_response": order_resp,
            "mode": self.mode,
        })

        # Track in memory
        managed = ManagedOrder(
            order_id=order_id,
            intent_group_id=intent_id,
            symbol=symbol,
            side=side,
            notional=notional,
            qty=qty,
            limit_price=limit_price,
            status=status,
            replace_count=replace_count,
            parent_order_id=parent_order_id,
            submitted_at=time.monotonic(),
            ttl_seconds=ttl,
        )
        self._orders[order_id] = managed

        self._emit_event(
            order_id=order_id,
            intent_group_id=intent_id,
            event_type="submitted",
            from_status=None,
            to_status=status,
            limit_price=limit_price,
        )

        return order_id

    async def poll_and_manage(self, get_price: Any = None) -> None:
        """Called every tick. Polls broker status, detects changes, triggers repositions.

        Args:
            get_price: callable(symbol) -> dict with 'bid', 'ask', 'mid', 'spread_pct'
        """
        for order_id in list(self._orders.keys()):
            managed = self._orders.get(order_id)
            if not managed:
                continue

            if managed.status in TERMINAL_STATES:
                continue

            # Poll broker for current status
            try:
                broker_state = await self.broker.get_order(order_id)
            except Exception:
                continue

            new_status = broker_state.get("status", managed.status)

            # Detect state change
            if new_status != managed.status:
                old_status = managed.status
                managed.status = new_status
                self.repo.update_order_status(order_id, new_status, broker_state)
                self._emit_event(
                    order_id=order_id,
                    intent_group_id=managed.intent_group_id,
                    event_type="status_change",
                    from_status=old_status,
                    to_status=new_status,
                )

                # Terminal: remove from tracking
                if new_status in TERMINAL_STATES:
                    if new_status == "filled":
                        self._complete_intent(managed.intent_group_id, "filled")
                    elif new_status in ("rejected", "failed"):
                        self._complete_intent(managed.intent_group_id, "failed")
                    del self._orders[order_id]
                    continue

            # Check TTL for reposition
            if managed.status in OPEN_STATES and get_price is not None:
                age = time.monotonic() - managed.submitted_at
                if age >= managed.ttl_seconds:
                    await self._try_reposition(managed, get_price)

    async def _try_reposition(self, managed: ManagedOrder, get_price: Any) -> None:
        """Attempt to cancel and replace a stale order."""
        price_data = get_price(managed.symbol)
        if not price_data:
            return

        decision = self.policy.should_reposition(
            side=managed.side,
            replace_count=managed.replace_count,
            current_limit=managed.limit_price,
            bid=price_data.get("bid", 0),
            ask=price_data.get("ask", 0),
            spread_pct=price_data.get("spread_pct", 0),
        )

        if decision == RepositionDecision.HOLD:
            return

        if decision == RepositionDecision.CANCEL:
            await self.cancel_order(managed.order_id, reason="max_reprices_exceeded")
            self._complete_intent(managed.intent_group_id, "exhausted")
            return

        if decision == RepositionDecision.CANCEL_LIQUIDITY:
            await self.cancel_order(managed.order_id, reason="liquidity_guard")
            self._complete_intent(managed.intent_group_id, "liquidity_guard")
            return

        # REPOSITION: cancel current, submit replacement
        new_price = self.policy.compute_new_price(
            side=managed.side,
            current_limit=managed.limit_price,
            bid=price_data.get("bid", 0),
            ask=price_data.get("ask", 0),
            replace_count=managed.replace_count,
        )

        await self.cancel_order(managed.order_id, reason="ttl_reposition")

        new_ttl = self.policy.ttl_for(managed.side, "entry")
        await self._submit_order(
            intent_id=managed.intent_group_id,
            symbol=managed.symbol,
            side=managed.side,
            notional=managed.notional,
            qty=managed.remaining_qty or managed.qty,
            order_type="limit",
            limit_price=new_price,
            replace_count=managed.replace_count + 1,
            parent_order_id=managed.order_id,
            ttl=new_ttl,
        )

    async def cancel_order(self, order_id: str, reason: str = "manual") -> None:
        """Cancel an order with a reason code."""
        managed = self._orders.get(order_id)
        if not managed:
            return

        old_status = managed.status
        managed.status = "cancel_pending"

        try:
            await self.broker.cancel_order(order_id)
        except Exception:
            pass

        self.repo.update_order_status(order_id, "canceled", {"cancel_reason": reason})
        managed.status = "canceled"

        self._emit_event(
            order_id=order_id,
            intent_group_id=managed.intent_group_id,
            event_type="canceled",
            from_status=old_status,
            to_status="canceled",
            reason=reason,
        )

        del self._orders[order_id]

    def get_pending_notional(self, side: str | None = None) -> float:
        """Sum notional for all non-terminal orders, optionally filtered by side."""
        total = 0.0
        for managed in self._orders.values():
            if managed.status in TERMINAL_STATES:
                continue
            if side and managed.side != side:
                continue
            total += managed.notional
        return total

    def recover_from_db(self) -> None:
        """On boot, load WORKING/PARTIAL/CANCEL_PENDING orders and resume tracking."""
        open_orders = self.repo.list_open_orders(self.mode)
        for order_data in open_orders:
            order_id = order_data.get("id", "")
            managed = ManagedOrder(
                order_id=order_id,
                intent_group_id=order_data.get("intent_group_id", ""),
                symbol=order_data.get("symbol", ""),
                side=order_data.get("side", "buy"),
                notional=float(order_data.get("notional", 0)),
                qty=float(order_data.get("qty", 0)) if order_data.get("qty") else None,
                limit_price=float(order_data.get("limit_price", 0)) if order_data.get("limit_price") else None,
                status=order_data.get("status", "submitted"),
                replace_count=int(order_data.get("replace_count", 0)),
                parent_order_id=order_data.get("parent_order_id"),
                submitted_at=time.monotonic(),  # approximate
                ttl_seconds=int(order_data.get("ttl_seconds", 60)),
            )
            self._orders[order_id] = managed

    def _complete_intent(self, intent_id: str, final_status: str) -> None:
        """Mark an intent as completed."""
        if intent_id in self._intents:
            self._intents[intent_id]["status"] = final_status
            self._intents[intent_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

    def _emit_event(
        self,
        *,
        order_id: str,
        intent_group_id: str,
        event_type: str,
        from_status: str | None,
        to_status: str,
        limit_price: float | None = None,
        filled_qty: float | None = None,
        filled_price: float | None = None,
        reason: str | None = None,
    ) -> None:
        """Emit an order event for persistence and UI streaming."""
        event = {
            "order_id": order_id,
            "intent_group_id": intent_group_id,
            "event_type": event_type,
            "from_status": from_status,
            "to_status": to_status,
            "limit_price": limit_price,
            "filled_qty": filled_qty,
            "filled_price": filled_price,
            "reason": reason,
            "mode": self.mode,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if self._on_event:
            try:
                self._on_event(event)
            except Exception:
                pass
