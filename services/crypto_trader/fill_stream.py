"""
Fill Stream Service — bridges Kraken WS execution events to FIFO/orders/fees.

Responsibilities:
1. Register as callback on KrakenWebSocket.on_execution()
2. Parse Kraken execution messages (snapshot vs update)
3. For each fill: write to local_fills → feed FIFO matcher → record fee
4. For status changes: update order status in local store
5. REST polling fallback every 30s for working orders (safety net)
6. Fill deduplication via fill_id primary key (idempotent)

Usage:
    fill_stream = FillStreamService(ws, exchange, fifo_matcher, local_store, sb, fee_tracker, order_mgr)
    await fill_stream.start()
    ...
    await fill_stream.stop()
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from integrations.kraken_client.ws import KrakenWebSocket
    from integrations.kraken_client.client import KrakenClient
    from services.accounting.fifo_matcher import FIFOMatcher
    from services.accounting.fee_tracker import FeeTracker
    from services.local_store import LocalEventStore
    from services.crypto_trader.order_manager import OrderManager

logger = logging.getLogger(__name__)

# REST fallback poll interval
REST_FALLBACK_SEC = 30


class FillStreamService:
    """Processes Kraken WS execution events into fills, FIFO matches, and status updates."""

    def __init__(
        self,
        ws: KrakenWebSocket,
        exchange: KrakenClient,
        fifo_matcher: FIFOMatcher,
        local_store: LocalEventStore,
        supabase_client: Any,
        fee_tracker: FeeTracker,
        order_manager: OrderManager | None = None,
        mode: str = "live",
    ) -> None:
        self._ws = ws
        self._exchange = exchange
        self._fifo = fifo_matcher
        self._store = local_store
        self._sb = supabase_client
        self._fee_tracker = fee_tracker
        self._order_mgr = order_manager
        self._mode = mode
        self._running = False
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._processor_task: asyncio.Task | None = None
        self._fallback_task: asyncio.Task | None = None
        self._fill_count = 0

    async def start(self) -> None:
        """Register WS callback and start background tasks."""
        self._running = True

        # Register execution callback on the WS
        self._ws.on_execution(self._on_execution_event)
        logger.info("Fill stream: registered WS execution callback")

        # Start async processor (consumes queue)
        self._processor_task = asyncio.create_task(self._process_loop())

        # Start REST fallback loop
        self._fallback_task = asyncio.create_task(self._rest_fallback_loop())

        logger.info("Fill stream: started (mode=%s)", self._mode)

    async def stop(self) -> None:
        """Stop all background tasks."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        if self._fallback_task:
            self._fallback_task.cancel()
            try:
                await self._fallback_task
            except asyncio.CancelledError:
                pass
        logger.info("Fill stream: stopped (%d fills processed)", self._fill_count)

    # ── WS Callback (sync → queues for async processing) ────────

    def _on_execution_event(self, data: dict[str, Any]) -> None:
        """Callback from WS. Queues events for async processing.

        Kraken WS v2 executions message format:
        {
            "channel": "executions",
            "type": "snapshot" | "update",
            "data": [
                {
                    "exec_type": "trade" | "pending_new" | "new" | "canceled" | "filled" | ...,
                    "order_id": "O...",
                    "exec_id": "T...",   # trade ID (for fills)
                    "symbol": "BTC/USD", # WS v2 format
                    "side": "buy" | "sell",
                    "last_qty": "0.001", # filled quantity on this execution
                    "last_price": "69000.00",
                    "fee_paid": "0.25",
                    "fee_currency": "USD",
                    "order_status": "new" | "partially_filled" | "filled" | "canceled",
                    "order_qty": "0.001",
                    "cum_qty": "0.001",   # total filled
                    "avg_price": "69000",
                    "timestamp": "2026-02-15T03:00:00.000Z",
                }
            ]
        }
        """
        msg_type = data.get("type", "")
        items = data.get("data", [])

        for item in items:
            try:
                self._event_queue.put_nowait(item)
            except asyncio.QueueFull:
                logger.warning("Fill stream: event queue full, dropping event")

        if msg_type == "snapshot":
            logger.info("Fill stream: received snapshot with %d items", len(items))
        elif items:
            logger.debug("Fill stream: received %d execution events", len(items))

    # ── Async Processing Loop ──────────────────────────────────

    async def _process_loop(self) -> None:
        """Consume events from the queue and process them."""
        while self._running:
            try:
                item = await asyncio.wait_for(
                    self._event_queue.get(), timeout=5.0
                )
                await self._process_execution(item)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Fill stream: processing error: %s", e, exc_info=True)

    async def _process_execution(self, exec_data: dict[str, Any]) -> None:
        """Process a single execution event."""
        exec_type = exec_data.get("exec_type", "")
        order_id = exec_data.get("order_id", "")

        if exec_type == "trade":
            # This is a fill — the most important event
            await self._handle_fill(exec_data)

        # Always update order status if we have a status
        order_status = exec_data.get("order_status", "")
        if order_id and order_status:
            self._store.update_order_status(
                order_id,
                self._normalize_status(order_status),
                {
                    "filled_qty": float(exec_data.get("cum_qty", 0)),
                    "filled_avg_price": float(exec_data.get("avg_price", 0)),
                },
            )

    async def _handle_fill(self, exec_data: dict[str, Any]) -> None:
        """Process a trade execution (fill)."""
        from integrations.kraken_client.symbols import from_kraken

        fill_id = exec_data.get("exec_id", "")
        if not fill_id:
            logger.warning("Fill stream: trade event missing exec_id")
            return

        # Deduplication check
        if self._store.fill_exists(fill_id):
            logger.debug("Fill stream: duplicate fill %s, skipping", fill_id)
            return

        # Parse fill data
        raw_symbol = exec_data.get("symbol", "")
        symbol = from_kraken(raw_symbol) if "/" in raw_symbol else raw_symbol
        side = exec_data.get("side", "")
        qty = float(exec_data.get("last_qty", 0))
        price = float(exec_data.get("last_price", 0))
        fee = float(exec_data.get("fee_paid", 0))
        fee_currency = exec_data.get("fee_currency", "USD")
        order_id = exec_data.get("order_id", "")

        # Validate fill data
        if qty <= 0 or price <= 0:
            logger.warning(
                "Fill stream: invalid fill data (qty=%.8f, price=%.2f) for %s",
                qty, price, fill_id,
            )
            return

        # Parse timestamp
        ts_raw = exec_data.get("timestamp", "")
        if ts_raw:
            executed_at = ts_raw
        else:
            executed_at = datetime.now(timezone.utc).isoformat()

        cost = qty * price

        fill = {
            "fill_id": fill_id,
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "fee": fee,
            "fee_currency": fee_currency,
            "cost": cost,
            "executed_at": executed_at,
            "mode": self._mode,
            "raw": exec_data,
        }

        # 1. Write to local store (idempotent)
        self._store.upsert_fill(fill)

        # 2. Feed FIFO matcher
        self._fifo.process_fill(
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            fee=fee,
            fill_id=fill_id,
            executed_at=executed_at,
        )

        # 3. Record fee
        try:
            await self._fee_tracker.record_fee(
                fill_id=fill_id,
                order_id=order_id,
                symbol=symbol,
                fee_amount=fee,
                fee_currency=fee_currency,
                fee_type="trading",
                mode=self._mode,
            )
        except Exception as e:
            logger.warning("Fill stream: fee recording failed: %s", e)

        # 4. Emit event to local store for flush
        self._store.insert_event(
            mode=self._mode,
            source="fill_stream",
            type="TRADE",
            subtype=f"{'BUY' if side == 'buy' else 'SELL'}_FILLED",
            symbol=symbol,
            body=f"Filled {qty} {symbol} @ ${price:.2f} (fee: ${fee:.4f})",
            meta={
                "fill_id": fill_id,
                "order_id": order_id,
                "qty": qty,
                "price": price,
                "fee": fee,
                "cost": cost,
            },
        )

        self._fill_count += 1
        logger.info(
            "FILL: %s %s %.8f @ $%.2f (fee: $%.4f) [%s]",
            side.upper(),
            symbol,
            qty,
            price,
            fee,
            fill_id,
        )

    # ── REST Fallback Loop ─────────────────────────────────────

    async def _rest_fallback_loop(self) -> None:
        """Every N seconds, poll REST for fills on any working orders as safety net.

        This catches fills that might be missed if the WS disconnects briefly.
        """
        while self._running:
            try:
                await asyncio.sleep(REST_FALLBACK_SEC)
                if not self._running:
                    break

                open_orders = self._store.get_open_orders(self._mode)
                if not open_orders:
                    continue

                for order in open_orders:
                    order_id = order.get("broker_order_id") or order.get("order_id")
                    if not order_id:
                        continue

                    try:
                        resp = await self._exchange.get_order_fills(order_id)
                        fills = resp.get("results", [])
                        for fill in fills:
                            fill_id = fill.get("fill_id", fill.get("id", ""))
                            if fill_id and not self._store.fill_exists(fill_id):
                                # Missed fill — process it now
                                logger.warning(
                                    "REST fallback: found missed fill %s for order %s",
                                    fill_id,
                                    order_id,
                                )
                                await self._handle_rest_fill(fill, order)
                    except Exception as e:
                        logger.debug("REST fallback poll error for %s: %s", order_id, e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("REST fallback loop error: %s", e)

    async def _handle_rest_fill(self, fill: dict[str, Any], order: dict[str, Any]) -> None:
        """Process a fill discovered via REST polling."""
        exec_data = {
            "exec_type": "trade",
            "exec_id": fill.get("fill_id", fill.get("id", "")),
            "order_id": fill.get("order_id", order.get("order_id", "")),
            "symbol": fill.get("symbol", order.get("symbol", "")),
            "side": fill.get("side", order.get("side", "")),
            "last_qty": str(fill.get("qty", fill.get("quantity", 0))),
            "last_price": str(fill.get("price", 0)),
            "fee_paid": str(fill.get("fee", 0)),
            "fee_currency": fill.get("fee_currency", "USD"),
            "timestamp": fill.get("executed_at", ""),
        }
        await self._handle_fill(exec_data)

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _normalize_status(kraken_status: str) -> str:
        """Normalize Kraken order status to our internal status."""
        mapping = {
            "new": "submitted",
            "pending_new": "submitted",
            "partially_filled": "partially_filled",
            "filled": "filled",
            "canceled": "cancelled",
            "expired": "expired",
        }
        return mapping.get(kraken_status, kraken_status)

    @property
    def fill_count(self) -> int:
        return self._fill_count
