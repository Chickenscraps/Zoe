"""Repositioner — detects stale orders and replaces them with updated prices.

Stale order detection:
- Checks every 30s for orders older than TTL
- Cancels stale order on exchange
- Refreshes quote from market_snapshot_focus
- Submits replacement at widened price (chase_step_pct * step_number)
- Max repositioning attempts configurable (default 3)
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class RepositionerConfig:
    """Configuration for the repositioner."""

    def __init__(self) -> None:
        self.check_interval_sec = int(os.getenv("REPO_CHECK_INTERVAL_SEC", "30"))
        self.order_ttl_sec = int(os.getenv("REPO_ORDER_TTL_SEC", "120"))
        self.chase_step_pct = float(os.getenv("REPO_CHASE_STEP_PCT", "0.05"))
        self.max_attempts = int(os.getenv("REPO_MAX_ATTEMPTS", "3"))


class Repositioner:
    """Monitors active order intents and replaces stale ones.

    Operates on order_intents rows in status 'submitted' or 'acked'.
    When an order exceeds TTL:
    1. Cancel on exchange
    2. Fetch fresh mark from focus snapshots
    3. Compute new limit price (widened by chase_step_pct * attempt)
    4. Create replacement intent
    """

    def __init__(
        self,
        supabase_client: Any,
        exchange_client: Any,
        intent_manager: Any,
        event_log: Any,
        config: RepositionerConfig | None = None,
    ):
        self._sb = supabase_client
        self._exchange = exchange_client
        self._intents = intent_manager
        self._events = event_log
        self.config = config or RepositionerConfig()
        self._running = False

    async def start(self) -> None:
        """Start the repositioner loop."""
        self._running = True
        logger.info(
            "Repositioner started (TTL=%ds, chase=%.3f%%, max=%d)",
            self.config.order_ttl_sec,
            self.config.chase_step_pct,
            self.config.max_attempts,
        )
        while self._running:
            try:
                await self._check_stale_orders()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Repositioner error: %s", e)
            await asyncio.sleep(self.config.check_interval_sec)

    async def stop(self) -> None:
        self._running = False

    async def _check_stale_orders(self) -> None:
        """Find and reposition stale orders."""
        try:
            resp = self._sb.table("order_intents").select("*").in_(
                "status", ["submitted", "acked"]
            ).execute()
            intents = resp.data or []
        except Exception as e:
            logger.warning("Stale order check failed: %s", e)
            return

        now = datetime.now(timezone.utc)

        for intent in intents:
            created = intent.get("created_at", "")
            if not created:
                continue

            try:
                ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            age_sec = (now - ts).total_seconds()
            if age_sec < self.config.order_ttl_sec:
                continue

            # Check reposition attempt count
            attempts = intent.get("metadata", {}).get("reposition_attempts", 0)
            if attempts >= self.config.max_attempts:
                logger.info(
                    "Max repositions reached for %s (%s), cancelling",
                    intent["symbol"], intent["id"],
                )
                await self._cancel_intent(intent)
                continue

            await self._reposition(intent, attempts)

    async def _reposition(self, intent: dict[str, Any], attempts: int) -> None:
        """Cancel stale order and submit replacement."""
        symbol = intent["symbol"]
        intent_id = intent["id"]
        broker_id = intent.get("broker_order_id")

        logger.info(
            "Repositioning %s order %s (age > %ds, attempt %d)",
            symbol, intent_id[:8], self.config.order_ttl_sec, attempts + 1,
        )

        # 1. Cancel on exchange
        if broker_id:
            try:
                await self._exchange.cancel_order(broker_id)
                await self._events.log_event(
                    intent_id, "cancel_for_reposition",
                    broker_order_id=broker_id,
                    metadata={"attempt": attempts + 1},
                )
            except Exception as e:
                logger.warning("Cancel failed for %s: %s", broker_id, e)
                return

        # 2. Update intent status
        await self._intents.update_status(intent_id, "cancelled")
        await self._events.log_event(intent_id, "cancelled")

        # 3. Fetch fresh mark
        mark = await self._get_mark(symbol)
        if mark <= 0:
            logger.warning("No mark price for %s, skipping reposition", symbol)
            return

        # 4. Compute widened price
        step = self.config.chase_step_pct / 100.0
        old_limit = float(intent.get("limit_price", 0)) or mark
        side = intent["side"]

        if side == "buy":
            new_limit = old_limit * (1 + step * (attempts + 1))
        else:
            new_limit = old_limit * (1 - step * (attempts + 1))

        # 5. Create replacement intent
        remaining_qty = intent.get("qty", 0)
        filled_qty = intent.get("fill_qty") or 0
        if filled_qty > 0 and remaining_qty:
            remaining_qty = float(remaining_qty) - float(filled_qty)

        new_intent = await self._intents.create_intent(
            symbol=symbol,
            side=side,
            order_type=intent.get("order_type", "limit"),
            qty=remaining_qty if remaining_qty and float(remaining_qty) > 0 else None,
            notional=intent.get("notional"),
            limit_price=new_limit,
            engine=intent.get("engine", ""),
            mode=intent.get("mode", "paper"),
            metadata={
                "parent_intent_id": intent_id,
                "reposition_attempts": attempts + 1,
                "original_limit": float(intent.get("limit_price", 0)),
            },
        )

        # Mark original as replaced
        await self._intents.update_status(intent_id, "replaced")
        await self._events.log_event(
            intent_id, "replaced",
            metadata={
                "new_intent_id": new_intent.id,
                "new_limit": new_limit,
                "attempt": attempts + 1,
            },
        )

        logger.info(
            "Repositioned %s: %s → %s (limit %.6f → %.6f)",
            symbol, intent_id[:8], new_intent.id[:8], old_limit, new_limit,
        )

    async def _cancel_intent(self, intent: dict[str, Any]) -> None:
        """Cancel an intent and its exchange order."""
        broker_id = intent.get("broker_order_id")
        if broker_id:
            try:
                await self._exchange.cancel_order(broker_id)
            except Exception as e:
                logger.warning("Cancel failed: %s", e)

        await self._intents.update_status(intent["id"], "cancelled")
        await self._events.log_event(
            intent["id"], "cancelled_max_attempts",
            metadata={"attempts": intent.get("metadata", {}).get("reposition_attempts", 0)},
        )

    async def _get_mark(self, symbol: str) -> float:
        """Get mark price from focus snapshots."""
        try:
            resp = self._sb.table("market_snapshot_focus").select(
                "mid"
            ).eq("symbol", symbol).maybeSingle().execute()
            if resp.data:
                return float(resp.data.get("mid", 0))
        except Exception:
            pass
        return 0.0
