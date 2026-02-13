from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import EdgeFactoryConfig
from .execution_policy import ExecutionMode, ExecutionParams
from .quote_model import QuoteModel

logger = logging.getLogger(__name__)


@dataclass
class OrderTicket:
    """Tracks the full lifecycle of a single order."""

    client_order_id: str
    symbol: str
    side: str  # "buy" or "sell"
    size_usd: float
    limit_price: float
    ttl_seconds: int
    max_retries: int
    execution_mode: ExecutionMode
    order_id: str = ""
    retries_used: int = 0
    status: str = "pending"  # pending | submitted | filled | partial | cancelled | failed
    fill_price: float | None = None
    filled_qty: float | None = None
    reference_mid: float = 0.0
    bid_at_submit: float = 0.0
    ask_at_submit: float = 0.0
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SlippageRecord:
    """Slippage measurement for a single fill."""

    symbol: str
    side: str
    reference_mid: float
    fill_price: float
    bid_at_submit: float
    ask_at_submit: float
    slippage_vs_mid_bps: float
    slippage_vs_bbo_bps: float
    spread_at_submit_bps: float
    execution_mode: str
    filled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OrderManager:
    """
    Manages order lifecycle with cancel/replace logic and slippage tracking.

    For a $150 account, every basis point of slippage matters.
    This manager provides:
    - Cancel/replace loop with configurable TTL and retries
    - Partial fill acceptance (don't re-submit remainder for tiny account)
    - Slippage measurement vs reference_mid and BBO at submit
    - Rolling slippage history for safety gate checks
    """

    def __init__(
        self,
        rh_client: Any,
        quote_model: QuoteModel,
        config: EdgeFactoryConfig,
    ):
        self.rh = rh_client
        self.quotes = quote_model
        self.config = config
        self.slippage_history: deque[SlippageRecord] = deque(maxlen=100)

    async def execute(
        self,
        symbol: str,
        side: str,
        size_usd: float,
        params: ExecutionParams,
        reference_mid: float,
    ) -> OrderTicket:
        """
        Full order lifecycle: submit -> poll -> cancel/replace if needed.

        Returns completed OrderTicket with fill details (or failure status).
        """
        quote = self.quotes.latest_unchecked(symbol)
        bid_at_submit = quote.bid if quote else 0.0
        ask_at_submit = quote.ask if quote else 0.0

        ticket = OrderTicket(
            client_order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            size_usd=size_usd,
            limit_price=params.limit_price,
            ttl_seconds=params.ttl_seconds,
            max_retries=params.max_retries,
            execution_mode=params.mode,
            reference_mid=reference_mid,
            bid_at_submit=bid_at_submit,
            ask_at_submit=ask_at_submit,
        )

        # Submit initial order
        ticket = await self._submit_order(ticket)
        if ticket.status == "failed":
            return ticket

        # Manage lifecycle: poll + cancel/replace
        ticket = await self._manage_lifecycle(ticket)

        # Record slippage if filled
        if ticket.status == "filled" and ticket.fill_price is not None:
            self._record_slippage(ticket)

        return ticket

    async def _submit_order(self, ticket: OrderTicket) -> OrderTicket:
        """Place order via RH client."""
        try:
            order_kwargs: dict[str, Any] = {
                "symbol": ticket.symbol,
                "side": ticket.side,
                "order_type": "limit",
                "client_order_id": ticket.client_order_id,
                "limit_price": ticket.limit_price,
            }

            if ticket.side == "buy":
                order_kwargs["notional"] = ticket.size_usd
            else:
                # For sells, compute qty from size and limit price
                qty = ticket.size_usd / ticket.limit_price if ticket.limit_price > 0 else 0
                order_kwargs["qty"] = qty

            order = await self.rh.place_order(**order_kwargs)
            ticket.order_id = order.get("id", ticket.client_order_id)
            ticket.status = "submitted"
            ticket.submitted_at = datetime.now(timezone.utc)

            logger.info(
                "ORDER SUBMITTED: %s %s %s $%.2f @ limit %.4f (mode=%s)",
                ticket.side.upper(), ticket.symbol, ticket.order_id,
                ticket.size_usd, ticket.limit_price, ticket.execution_mode.value,
            )

        except Exception as e:
            logger.error("ORDER SUBMIT FAILED: %s %s: %s", ticket.side, ticket.symbol, e)
            ticket.status = "failed"

        return ticket

    async def _manage_lifecycle(self, ticket: OrderTicket) -> OrderTicket:
        """Poll for fill, cancel/replace if TTL expires."""
        poll_interval = 3  # seconds

        while ticket.retries_used <= ticket.max_retries:
            elapsed = 0

            while elapsed < ticket.ttl_seconds:
                try:
                    order = await self.rh.get_order(ticket.order_id)
                    status = order.get("status", "")

                    if status == "filled":
                        fills = await self.rh.get_order_fills(ticket.order_id)
                        fill_list = fills.get("results", [])
                        if fill_list:
                            ticket.fill_price = float(fill_list[0].get("price", ticket.limit_price))
                            ticket.filled_qty = float(fill_list[0].get("quantity", 0))
                        else:
                            ticket.fill_price = float(order.get("price", ticket.limit_price))
                        ticket.status = "filled"
                        logger.info(
                            "ORDER FILLED: %s %s @ %.4f",
                            ticket.symbol, ticket.order_id, ticket.fill_price,
                        )
                        return ticket

                    if status == "partially_filled":
                        # Accept partial for small account — don't chase remainder
                        fills = await self.rh.get_order_fills(ticket.order_id)
                        fill_list = fills.get("results", [])
                        if fill_list:
                            ticket.fill_price = float(fill_list[0].get("price", ticket.limit_price))
                            ticket.filled_qty = float(fill_list[0].get("quantity", 0))
                        ticket.status = "filled"  # Treat partial as filled
                        logger.info(
                            "ORDER PARTIAL FILL (accepted): %s @ %.4f",
                            ticket.symbol, ticket.fill_price or 0,
                        )
                        return ticket

                    if status in {"canceled", "rejected", "failed"}:
                        ticket.status = "cancelled"
                        logger.warning("ORDER %s: %s %s", status.upper(), ticket.symbol, ticket.order_id)
                        return ticket

                except Exception as e:
                    logger.warning("Order poll error: %s", e)

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            # TTL expired — attempt cancel/replace
            if ticket.retries_used < ticket.max_retries:
                logger.info(
                    "ORDER TTL EXPIRED: %s — cancel/replace attempt %d/%d",
                    ticket.symbol, ticket.retries_used + 1, ticket.max_retries,
                )

                # Refresh quote and widen buffer
                try:
                    quote = await self.quotes.refresh(ticket.symbol)
                    # Widen price by one step (0.05%) per retry
                    step = 0.0005 * (ticket.retries_used + 1)
                    if ticket.side == "buy":
                        ticket.limit_price = quote.bid * (1.0 + step)
                    else:
                        ticket.limit_price = quote.bid * (1.0 - step)

                    # Generate new client_order_id for replacement
                    ticket.client_order_id = str(uuid.uuid4())
                    ticket = await self._submit_order(ticket)
                    if ticket.status == "failed":
                        return ticket

                except Exception as e:
                    logger.warning("Cancel/replace failed: %s", e)
                    ticket.status = "failed"
                    return ticket

            ticket.retries_used += 1

        # Exhausted all retries
        ticket.status = "cancelled"
        logger.warning("ORDER EXHAUSTED RETRIES: %s %s", ticket.symbol, ticket.order_id)
        return ticket

    def _record_slippage(self, ticket: OrderTicket) -> None:
        """Compute and store slippage metrics."""
        fill = ticket.fill_price
        if fill is None or fill <= 0:
            return

        mid = ticket.reference_mid
        bid = ticket.bid_at_submit
        ask = ticket.ask_at_submit

        if mid <= 0:
            return

        # Slippage vs mid (in basis points)
        if ticket.side == "buy":
            slippage_vs_mid = (fill - mid) / mid * 10000
            slippage_vs_bbo = (fill - ask) / ask * 10000 if ask > 0 else 0
        else:
            slippage_vs_mid = (mid - fill) / mid * 10000
            slippage_vs_bbo = (bid - fill) / bid * 10000 if bid > 0 else 0

        spread_bps = (ask - bid) / mid * 10000 if mid > 0 else 0

        record = SlippageRecord(
            symbol=ticket.symbol,
            side=ticket.side,
            reference_mid=mid,
            fill_price=fill,
            bid_at_submit=bid,
            ask_at_submit=ask,
            slippage_vs_mid_bps=round(slippage_vs_mid, 2),
            slippage_vs_bbo_bps=round(slippage_vs_bbo, 2),
            spread_at_submit_bps=round(spread_bps, 2),
            execution_mode=ticket.execution_mode.value,
        )

        self.slippage_history.append(record)
        logger.info(
            "SLIPPAGE: %s %s mid_slip=%.1fbps bbo_slip=%.1fbps spread=%.1fbps",
            ticket.side.upper(), ticket.symbol,
            slippage_vs_mid, slippage_vs_bbo, spread_bps,
        )

    def avg_slippage_bps(self, window: int = 20) -> float:
        """Average slippage vs mid over last N fills."""
        recent = list(self.slippage_history)[-window:]
        if not recent:
            return 0.0
        return sum(r.slippage_vs_mid_bps for r in recent) / len(recent)

    def check_slippage_gate(self) -> tuple[bool, float]:
        """
        Check if average slippage is within threshold.
        Returns (allowed, current_avg_bps).
        """
        avg = self.avg_slippage_bps()
        allowed = avg <= self.config.max_avg_slippage_bps
        return allowed, avg
