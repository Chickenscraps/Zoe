"""Equity calculator — mark-to-market portfolio valuation.

Equity = USD cash + SUM(position_qty * mark_price)

Mark prices sourced from market_snapshot_focus table (live WS data).
Falls back to exchange REST if focus snapshot is stale.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EquityBreakdown:
    """Detailed equity breakdown."""
    cash_usd: float
    crypto_value: float  # sum of qty * mark
    total_equity: float  # cash + crypto
    positions: list[PositionMark]
    realized_pnl: float
    unrealized_pnl: float
    total_fees: float


@dataclass
class PositionMark:
    """Single position with mark-to-market data."""
    symbol: str
    qty: float
    cost_basis: float  # avg cost per unit
    mark_price: float  # current market price
    market_value: float  # qty * mark
    unrealized_pnl: float  # (mark - cost_basis) * qty


class EquityCalculator:
    """
    Computes portfolio equity using mark-to-market pricing.

    Sources:
    - Cash: from exchange balance or latest cash snapshot
    - Positions: from FIFO matcher open lots
    - Marks: from market_snapshot_focus (Supabase) or exchange REST fallback
    """

    def __init__(self, supabase_client: Any, exchange_client: Any | None = None):
        self._sb = supabase_client
        self._exchange = exchange_client

    async def compute(
        self,
        cash_usd: float,
        fifo_matcher: Any,
        mode: str = "live",
    ) -> EquityBreakdown:
        """Compute full equity breakdown with mark-to-market.

        Args:
            cash_usd: Current USD cash balance.
            fifo_matcher: FIFOMatcher instance with current state.
            mode: Trading mode.

        Returns:
            EquityBreakdown with full position detail.
        """
        symbols = fifo_matcher.get_all_symbols()
        marks = await self._fetch_marks(symbols)

        positions: list[PositionMark] = []
        total_crypto = 0.0
        total_unrealized = 0.0

        for sym in symbols:
            qty = fifo_matcher.get_open_qty(sym)
            if qty <= 1e-12:
                continue

            cost_basis = fifo_matcher.get_cost_basis(sym)
            mark = marks.get(sym, 0.0)

            if mark <= 0:
                logger.warning("No mark price for %s, using cost basis", sym)
                mark = cost_basis

            market_value = qty * mark
            unrealized = fifo_matcher.get_unrealized_pnl(sym, mark)

            positions.append(PositionMark(
                symbol=sym,
                qty=qty,
                cost_basis=cost_basis,
                mark_price=mark,
                market_value=market_value,
                unrealized_pnl=unrealized,
            ))

            total_crypto += market_value
            total_unrealized += unrealized

        return EquityBreakdown(
            cash_usd=cash_usd,
            crypto_value=total_crypto,
            total_equity=cash_usd + total_crypto,
            positions=positions,
            realized_pnl=fifo_matcher.get_realized_pnl(),
            unrealized_pnl=total_unrealized,
            total_fees=fifo_matcher.get_total_fees(),
        )

    async def _fetch_marks(self, symbols: list[str]) -> dict[str, float]:
        """Fetch mark prices from focus snapshots, falling back to exchange."""
        marks: dict[str, float] = {}

        if not symbols:
            return marks

        # Try market_snapshot_focus first (fast, from WS pipeline)
        try:
            resp = self._sb.table("market_snapshot_focus").select(
                "symbol, mid"
            ).in_("symbol", symbols).execute()
            for row in (resp.data or []):
                mid = float(row.get("mid", 0))
                if mid > 0:
                    marks[row["symbol"]] = mid
        except Exception as e:
            logger.warning("Focus snapshot fetch failed: %s", e)

        # Fallback: exchange REST for any missing marks
        missing = [s for s in symbols if s not in marks]
        if missing and self._exchange:
            try:
                if hasattr(self._exchange, "get_best_bid_ask_batch"):
                    data = await self._exchange.get_best_bid_ask_batch(missing)
                    for sym, ticker in data.items():
                        bid = float(ticker.get("bid", 0))
                        ask = float(ticker.get("ask", 0))
                        if bid > 0 and ask > 0:
                            marks[sym] = (bid + ask) / 2.0
                else:
                    for sym in missing:
                        try:
                            data = await self._exchange.get_best_bid_ask(sym)
                            results = data.get("results", [])
                            if results:
                                entry = results[0]
                                bid = float(entry.get("bid", entry.get("bid_price", 0)))
                                ask = float(entry.get("ask", entry.get("ask_price", 0)))
                                if bid > 0 and ask > 0:
                                    marks[sym] = (bid + ask) / 2.0
                        except Exception:
                            pass
            except Exception as e:
                logger.warning("Exchange mark fetch failed: %s", e)

        return marks
