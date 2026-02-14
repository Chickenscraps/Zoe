"""FIFO cost-basis matching for realized P&L.

For each sell fill, pops the oldest buy lots (FIFO) and computes:
    realized = (sell_price - buy_price) * matched_qty - buy_fee_portion - sell_fee_portion

Tracks open lots per symbol for unrealized P&L calculation.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Lot:
    """A single buy lot (or portion thereof)."""
    symbol: str
    qty: float
    price: float
    fee: float  # total fee for this lot (prorated if split)
    fill_id: str = ""
    executed_at: str = ""


@dataclass
class MatchResult:
    """Result of matching a sell against buy lots."""
    symbol: str
    sell_qty: float
    sell_price: float
    sell_fee: float
    matched_lots: list[tuple[Lot, float]]  # (lot, matched_qty) pairs
    realized_pnl: float = 0.0


@dataclass
class FIFOState:
    """Per-symbol state: open lots + cumulative realized."""
    open_lots: deque[Lot] = field(default_factory=deque)
    realized_pnl: float = 0.0
    total_fees_paid: float = 0.0


class FIFOMatcher:
    """
    FIFO cost-basis matcher.

    Feed it fills in chronological order. It maintains open lots per symbol
    and computes realized P&L on sells.
    """

    def __init__(self) -> None:
        self._state: dict[str, FIFOState] = {}

    def process_fill(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        fee: float,
        fill_id: str = "",
        executed_at: str = "",
    ) -> MatchResult | None:
        """Process a single fill. Returns MatchResult for sells, None for buys."""
        if symbol not in self._state:
            self._state[symbol] = FIFOState()

        state = self._state[symbol]
        state.total_fees_paid += fee

        if side == "buy":
            lot = Lot(
                symbol=symbol,
                qty=qty,
                price=price,
                fee=fee,
                fill_id=fill_id,
                executed_at=executed_at,
            )
            state.open_lots.append(lot)
            return None

        # Sell: match against oldest buy lots (FIFO)
        remaining = qty
        matched: list[tuple[Lot, float]] = []
        realized = 0.0

        while remaining > 1e-12 and state.open_lots:
            lot = state.open_lots[0]

            if lot.qty <= remaining + 1e-12:
                # Consume entire lot
                match_qty = lot.qty
                remaining -= match_qty
                state.open_lots.popleft()
                # P&L for this match: (sell_price - buy_price) * qty
                realized += (price - lot.price) * match_qty
                matched.append((lot, match_qty))
            else:
                # Partial lot consumption
                match_qty = remaining
                # Prorate the lot fee
                fee_portion = lot.fee * (match_qty / lot.qty)
                realized += (price - lot.price) * match_qty
                # Reduce lot in place
                lot.fee -= fee_portion
                lot.qty -= match_qty
                remaining = 0
                matched.append((Lot(
                    symbol=lot.symbol,
                    qty=match_qty,
                    price=lot.price,
                    fee=fee_portion,
                    fill_id=lot.fill_id,
                    executed_at=lot.executed_at,
                ), match_qty))

        # Subtract sell fee from realized
        realized -= fee
        # Also subtract buy fees for matched lots
        buy_fees = sum(lot.fee for lot, _ in matched)
        realized -= buy_fees

        state.realized_pnl += realized

        if remaining > 1e-12:
            logger.warning(
                "FIFO: sold %.8f %s but only %.8f in buy lots (%.8f unmatched)",
                qty, symbol, qty - remaining, remaining,
            )

        result = MatchResult(
            symbol=symbol,
            sell_qty=qty,
            sell_price=price,
            sell_fee=fee,
            matched_lots=matched,
            realized_pnl=realized,
        )
        return result

    def get_realized_pnl(self, symbol: str | None = None) -> float:
        """Total realized P&L, optionally filtered by symbol."""
        if symbol:
            return self._state.get(symbol, FIFOState()).realized_pnl
        return sum(s.realized_pnl for s in self._state.values())

    def get_open_lots(self, symbol: str) -> list[Lot]:
        """Get open (unmatched) buy lots for a symbol."""
        state = self._state.get(symbol)
        if not state:
            return []
        return list(state.open_lots)

    def get_cost_basis(self, symbol: str) -> float:
        """Weighted average cost basis of open lots."""
        lots = self.get_open_lots(symbol)
        if not lots:
            return 0.0
        total_cost = sum(lot.qty * lot.price + lot.fee for lot in lots)
        total_qty = sum(lot.qty for lot in lots)
        if total_qty <= 0:
            return 0.0
        return total_cost / total_qty

    def get_open_qty(self, symbol: str) -> float:
        """Total open quantity for a symbol."""
        lots = self.get_open_lots(symbol)
        return sum(lot.qty for lot in lots)

    def get_total_fees(self, symbol: str | None = None) -> float:
        """Total fees paid, optionally filtered by symbol."""
        if symbol:
            return self._state.get(symbol, FIFOState()).total_fees_paid
        return sum(s.total_fees_paid for s in self._state.values())

    def get_all_symbols(self) -> list[str]:
        """All symbols with any activity."""
        return list(self._state.keys())

    def get_unrealized_pnl(self, symbol: str, mark_price: float) -> float:
        """Unrealized P&L for open lots at a given mark price."""
        lots = self.get_open_lots(symbol)
        if not lots:
            return 0.0
        pnl = 0.0
        for lot in lots:
            pnl += (mark_price - lot.price) * lot.qty - lot.fee
        return pnl

    @classmethod
    def from_fills(cls, fills: list[dict[str, Any]]) -> FIFOMatcher:
        """Build a FIFO matcher from a list of fill dicts (sorted by executed_at)."""
        matcher = cls()
        for fill in fills:
            matcher.process_fill(
                symbol=fill["symbol"],
                side=fill["side"],
                qty=float(fill["qty"]),
                price=float(fill["price"]),
                fee=float(fill.get("fee", 0)),
                fill_id=fill.get("fill_id", ""),
                executed_at=fill.get("executed_at", ""),
            )
        return matcher
